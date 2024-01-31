from django.shortcuts import HttpResponse, render
from django.db import connection
import datetime
import calendar
import json
from django.contrib.auth.decorators import login_required
from time_management.decorators import user_is_in_manager_group
from time_management.time_tools import get_user_list, get_all_users


@login_required
# @user_is_in_manager_group
def entries_home(request):
    users = None

    if request.user.is_staff:
        user_list = get_all_users()
    else:
        user_list = get_user_list(username=request.user.username, as_json=True)

    print("ENTRIES:", type(user_list))

    if len(user_list) > 1:
        users = user_list

    return render(request, 'time_entries.html', {
        'user_list': users,
        'start': (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%m/%d/%Y'),
        'end': datetime.datetime.now().strftime('%m/%d/%Y')
    })


@login_required
# @user_is_in_manager_group
def get_date_range(request):
    cur = connection.cursor()

    # gather a list of all years
    cur.execute("SELECT DISTINCT tyear FROM time_entries ORDER BY tyear;")
    dbyears = cur.fetchall()

    # gather a list of all months (should always be 1-12)
    cur.execute("SELECT DISTINCT tmonth FROM time_entries ORDER BY tmonth;")
    dbmonths = cur.fetchall()

    # loop through the years, constructing a year dictionary
    year_list = []
    for year in dbyears:
        new_year = {}  # haha...new year...
        new_year['year'] = year[0]
        year_list.append(new_year)

    # loop through the months, constructing a month dictionary
    month_list = []
    for month in dbmonths:
        new_month = {}
        new_month['number'] = month[0]
        new_month['name'] = calendar.month_name[month[0]]
        month_list.append(new_month)


    # if this is empty...give it SOMETHING...
    if len(month_list) == 0:
        month_list.append({'number': datetime.datetime.today().month, 'name': calendar.month_name[datetime.datetime.today().month]})

    if len(year_list) == 0:
        year_list.append({'year': datetime.datetime.today().year})

    context = {'months': month_list, 'years': year_list}
    return HttpResponse(json.dumps(context))


@login_required
# @user_is_in_manager_group
def get_project_activities(request):
    project = request.GET['project']

    # connect to the database
    cur = connection.cursor()

    # first get any that are specific to our project
    cur.execute(
        "SELECT name FROM enumerations WHERE type = 'TimeEntryActivity' and project_id = %(proj)s "
        "and active = FALSE;" % {
            'proj': project})
    exclusions = cur.fetchall()
    exclude_list = []
    for ex in exclusions:
        exclude_list.append(ex[0])

    # now get the defaults
    cur.execute(
        "SELECT id, name FROM enumerations WHERE type = 'TimeEntryActivity' and active = TRUE and project_id is NULL;")
    activity = cur.fetchall()

    activity_list = []
    for act in activity:
        if act[1] in exclude_list:
            continue
        active = {}
        active['id'] = act[0]
        active['name'] = act[1]
        activity_list.append(active)

    return HttpResponse(json.dumps(activity_list))


@login_required
# @user_is_in_manager_group
def update_entries(request):
    # grab our list of entries to update
    entries = json.loads(request.GET['entries'])

    # do we have any?
    if len(entries) == 0:
        return HttpResponse("Nothing to save")

    # grab their username
    user = request.user.username

    # connect to the database
    cur = connection.cursor()

    # let's do some security checks - run through each entry
    # and make sure they are the owner of each one...unless they're a manager!
    target = user
    if 'target' in request.GET and request.GET['target'] is not None and request.GET['target'] != '':
        target = request.GET['target']
    target_id = ''
    for entry in entries:
        if entry['id'] != 'new_entry':
            cur.execute(
                "SELECT users.login, users.id FROM users INNER JOIN time_entries "
                "ON time_entries.user_id = users.id WHERE time_entries.id = %(entry)s;" % {
                    'entry': entry['id']})
            userid = cur.fetchone()
            target = userid[0]
            target_id = userid[1]
            # get the list of users they're allowed to modify
            if not request.user.is_staff:
                user_list = get_user_list(username=request.user.username, as_json=True)
                if target_id not in user_list and (not request.user.is_staff):
                    return HttpResponse("Error 97")
        else:
            # otherwise, get the target_id
            cur.execute("SELECT users.login, users.id FROM users WHERE login = '%(user)s';" % {'user': target})
            userid = cur.fetchone()
            target = userid[0]
            target_id = userid[1]
            # get the list of users they're allowed to modify
            if not request.user.is_staff:
                user_list = get_user_list(username=request.user.username, as_json=True)
                if target_id not in user_list and (not request.user.is_staff):
                    return HttpResponse("Error 97")

    # now let's run through each entry and perform our update
    for entry in entries:
        # print entry
        # format the date properly
        edate = entry['date'].split('-')
        entry_date = datetime.date(int(edate[0]), int(edate[1]), int(edate[2]))

        # format the issue if emtpy
        issue = 'null'
        if entry['issue'] != '':
            issue = entry['issue']

        # grab the old record
        if entry['id'] != 'new_entry':
            query = "SELECT id, project_id, user_id, issue_id, hours, comments, activity_id, spent_on, " \
                    "tyear, tmonth, tweek, created_on, updated_on FROM time_entries WHERE id = %(id)s;" % {
                        'id': entry['id']}
            cur.execute(query)
            old_record = cur.fetchone()
        else:
            old_record = 'No Entry Existed'

        # check the entry's ID...if it is "new_entry", then we insert
        # otherwise we update
        if entry['id'] == 'new_entry':
            query = "INSERT INTO time_entries (project_id, user_id, spent_on, hours, comments, issue_id, " \
                    "activity_id, tyear, tmonth, tweek, created_on, updated_on) VALUES (%(project)s, %(user)s, " \
                    "'%(date)s', %(hours)s, '%(comments)s', %(issue)s, %(activity)s, %(year)s, %(month)s, " \
                    "%(week)s, '%(now)s', '%(now)s') RETURNING *;" % {
                        'project': entry['project'], 'user': target_id, 'date': entry['date'],
                        'hours': float(entry['hours']),
                        'comments': entry['comments'].replace("'", "''"), 'issue': issue, 'activity': entry['activity'],
                        'year': edate[0], 'month': edate[1], 'week': entry_date.isocalendar()[1],
                        'now': datetime.datetime.now().isoformat()}
        else:
            # construct the query
            query = "UPDATE time_entries SET project_id = %(project)s, spent_on = '%(date)s', hours = %(hours)s, " \
                    "comments = '%(comments)s', issue_id = %(issue)s, activity_id = %(activity)s, " \
                    "tyear = %(year)s, tmonth = %(month)s, tweek = %(week)s WHERE id = %(entry_id)s " \
                    "RETURNING *;" % {
                        'project': entry['project'], 'date': entry['date'], 'hours': float(entry['hours']),
                        'comments': entry['comments'].replace("'", "''"), 'issue': issue, 'activity': entry['activity'],
                        'entry_id': entry['id'], 'year': edate[0], 'month': edate[1],
                        'week': entry_date.isocalendar()[1]}

        # execute the query
        cur.execute(query)

        # grab the id, if we need it
        timeid = cur.fetchone()[0]

        if entry['id'] == 'new_entry':
            query = "INSERT INTO custom_values (customized_id, custom_field_id, value, customized_type) " \
                    "VALUES (%(id)s, (SELECT id FROM custom_fields WHERE lower(name) like '%%task%%'), '%(value)s', 'TimeEntry');" % {
                        'id': timeid, 'value': entry['logas']}
        else:
            query = "UPDATE custom_values SET value = '%(value)s' WHERE customized_id = %(id)s " \
                    "AND custom_field_id = (select id from custom_fields where lower(name) like '%%task%%') " \
                    "AND customized_type = 'TimeEntry';" % {
                        'id': entry['id'], 'value': entry['logas']}
        cur.execute(query)

        # if the user performing this action is NOT the target, let's record this change...
        if target != user:
            query = "INSERT INTO time_entry_log (\"user\", old_record, new_record, \"timestamp\", target) " \
                    "VALUES ('%(user)s', '%(old)s', '%(new)s', '%(time)s', '%(target)s');" % {
                        'user': user, 'old': str(old_record).replace('\'', ''), 'new': str(entry).replace('\'', ''),
                        'time': str(datetime.datetime.now()), 'target': target}
            cur.execute(query)

    # if we made it out ok, let's commit it!
    connection.commit()

    return HttpResponse("200")


@login_required
# @user_is_in_manager_group
def delete_entry(request):
    # grab our list of entries to update
    entry = json.loads(request.GET['entry'])

    # do we have any?
    if entry == '':
        return HttpResponse("Nothing to save")

    # grab their username
    user = request.user.username

    # connect to the database
    cur = connection.cursor()

    cur.execute(
        "SELECT users.login, users.id FROM users INNER JOIN time_entries "
        "ON time_entries.user_id = users.id WHERE time_entries.id = %(entry)s;" % {
            'entry': entry})
    userid = cur.fetchone()
    target = userid[0]
    target_id = userid[1]
    # get the list of users they're allowed to modify
    if not request.user.is_staff:
        user_list = get_user_list(username=request.user.username, as_json=True)
        if target_id not in user_list and (not request.user.is_staff):
            return HttpResponse("Error 97")

    # get a copy of that record in case we need to log it...
    cur.execute("SELECT * FROM time_entries WHERE id = %(id)s;" % {'id': entry})
    old_entry = cur.fetchone()

    # now simply delete it!
    cur.execute("DELETE FROM time_entries WHERE id = %(id)s;" % {'id': entry})

    # also delete any record in "custom_values"
    cur.execute("DELETE FROM custom_values WHERE customized_id = %(id)s;" % {'id': entry})

    # if the user performing this action is NOT the target, let's record this removal...
    if target != user:
        query = "INSERT INTO time_entry_log (\"user\", old_record, new_record, \"timestamp\", target) " \
                "VALUES ('%(user)s', '%(old)s', '%(new)s', '%(time)s', '%(target)s');" % {
                    'user': user, 'old': str(old_entry).replace('\'', ''), 'new': 'RECORD DELETED',
                    'time': str(datetime.datetime.now()), 'target': target}
        cur.execute(query)

    # commit!
    connection.commit()

    return HttpResponse("200")
