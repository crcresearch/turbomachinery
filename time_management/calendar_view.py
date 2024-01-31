from django.shortcuts import HttpResponse, render
from django.db import connection
import datetime
import json
from django.contrib.auth.decorators import login_required
from time_management.decorators import user_is_in_manager_group
from time_management.time_tools import get_user_list, get_all_users


@login_required
# @user_is_in_manager_group
def calendar_home(request):
    users = None

    if request.user.is_staff:
        user_list = get_all_users()
    else:
        user_list = get_user_list(username=request.user.username, as_json=True)

    print ("ENTRIES:", type(user_list))

    if len(user_list) > 1:
        users = user_list
    return render(request, 'calendar.html', {
        'user_list': users
    })


@login_required
# @user_is_in_manager_group
def update_entry_data(request):
    # grab their username
    user = request.user.username

    # connect to the database
    cur = connection.cursor()

    # let's do some security checks - run through each entry
    # and make sure they are the owner of each one...unless they're a manager!
    target = user
    if 'target' in request.GET and request.GET['target'] is not None and request.GET['target'] != '':
        target = request.GET['target']

    cur.execute("SELECT users.login, users.id FROM users WHERE login = '%(user)s';" % {'user': target})
    userid = cur.fetchone()
    target = userid[0]
    target_id = userid[1]

    if not request.user.is_staff:
        user_list = get_user_list(username=request.user.username, as_json=True)
        if target_id not in user_list and (not request.user.is_staff):
            return HttpResponse("Error 97")

    # format the date properly
    edate = request.GET['date'].split('-')
    entry_date = datetime.date(int(edate[0]), int(edate[1]), int(edate[2]))

    # construct the query
    query = "UPDATE time_entries SET project_id = (SELECT id FROM projects WHERE name='%(project)s'), spent_on = " \
            "'%(date)s', hours = %(hours)s, comments = '%(comments)s', activity_id = %(activity)s, " \
            "tyear = %(year)s, " \
            "tmonth = %(month)s, tweek = %(week)s WHERE id = %(entry_id)s RETURNING *;" % {
                    'project': request.GET['project'], 'date': request.GET['date'],
                    'hours': float(request.GET['hours']),
                    'comments': request.GET['comments'].replace("'", "''"), 'activity': request.GET['activity'],
                    'entry_id': request.GET['id'], 'year': edate[0], 'month': edate[1],
                    'week': entry_date.isocalendar()[1]}

    # execute the query
    cur.execute(query)

    # if we made it out ok, let's commit it!
    connection.commit()

    return HttpResponse("200")


@login_required
# @user_is_in_manager_group
def copy_entry(request):
    # grab their username
    user = request.user.username

    # connect to the database
    cur = connection.cursor()

    # let's do some security checks - run through each entry
    # and make sure they are the owner of each one...unless they're a manager!
    target = user
    if request.GET['target'] is not None and request.GET['target'] != '':
        target = request.GET['target']

    # make sure we're the owner of the one being copied
    cur.execute("SELECT users.login, users.id FROM users INNER JOIN time_entries ON time_entries.user_id = users.id "
                "WHERE time_entries.id = %(entry)s;" % {'entry': request.GET['entry_id']})
    userid = cur.fetchone()
    target = userid[0]
    target_id = userid[1]
    if (target != user) and (not request.user.is_staff):
        return HttpResponse("Error 97")

    # grab the record they want to copy
    query = "SELECT id, project_id, user_id, issue_id, hours, comments, activity_id, spent_on, tyear, tmonth, tweek " \
            "FROM time_entries WHERE id = %(id)s;" % {'id': request.GET['entry_id']}
    cur.execute(query)
    old_record = cur.fetchone()

    edate = request.GET['date'].split('-')
    entry_date = datetime.date(int(edate[0]), int(edate[1]), int(edate[2]))

    issue = 'null'
    if old_record[3] != 'None' and old_record[3] is not None:
        issue = old_record[3]

    # insert a new record with all of the same values, except change the spent_on entry
    query = "INSERT INTO time_entries (project_id, user_id, spent_on, hours, comments, issue_id, activity_id, tyear, " \
            "tmonth, tweek, created_on, updated_on) VALUES (%(project)s, %(user)s, '%(date)s', %(hours)s, " \
            "'%(comments)s', %(issue)s, %(activity)s, %(year)s, %(month)s, %(week)s, '%(now)s', '%(now)s') " \
            "RETURNING id;" % {'project': old_record[1], 'user': target_id, 'date': entry_date, 'hours': old_record[4],
                               'comments': old_record[5].replace("'", "''"), 'issue': issue, 'activity': old_record[6],
                               'year': edate[0], 'month': edate[1], 'week': entry_date.isocalendar()[1],
                               'now': datetime.datetime.now().isoformat()}

    cur.execute(query)
    new_id = cur.fetchone()[0]

    # also copy the custom_values
    query = "SELECT customized_type, custom_field_id, value FROM custom_values WHERE " \
            "customized_id = %(id)s;" % {'id': request.GET['entry_id']}
    cur.execute(query)
    custom_value = cur.fetchone()
    query = "INSERT INTO custom_values (customized_type, customized_id, custom_field_id, value) " \
            "VALUES ('%(type)s', %(id)s, %(field)s, '%(value)s');" % {'type': custom_value[0], 'id': new_id,
                                                                      'field': custom_value[1],
                                                                      'value': custom_value[2]}
    cur.execute(query)

    # get the records for this user, month, and year
    cur.execute("SELECT time_entries.id, time_entries.project_id, projects.name, time_entries.issue_id, "
                "time_entries.hours, time_entries.comments, enumerations.name, time_entries.spent_on, "
                "custom_values.value, enumerations.id, projects.id "
                "FROM time_entries "
                "INNER JOIN custom_values "
                "ON custom_values.customized_id = time_entries.id "
                "INNER JOIN users ON users.id = time_entries.user_id "
                "INNER JOIN projects ON projects.id = time_entries.project_id "
                "INNER JOIN enumerations ON enumerations.id = time_entries.activity_id "
                "WHERE time_entries.id = %(id)s;" % {'id': new_id})
    entry = cur.fetchone()

    new_entry = {}
    new_entry['id'] = entry[0]
    new_entry['project'] = entry[1]
    new_entry['name'] = entry[2]
    new_entry['issue'] = entry[3]
    new_entry['hours'] = entry[4]
    new_entry['comments'] = entry[5]
    new_entry['activity'] = entry[6]
    new_entry['date'] = entry[7].isoformat()
    new_entry['logas'] = entry[8]
    new_entry['activity_id'] = entry[9]
    new_entry['project_id'] = entry[10]

    connection.commit()

    return HttpResponse(json.dumps(new_entry))
