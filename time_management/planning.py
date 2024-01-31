import json

import datetime
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.shortcuts import HttpResponse, render

from time_management.time_tools import date_working_hours, manager_date_working_hours


@login_required
def planning_home(request):
    context = {}
    if not request.user.is_staff:
        return HttpResponse("I'm afraid I can't do that...")

    # get a list of active projects
    # connect to our database
    cur = connection.cursor()

    cur.execute("SELECT projects.id, name FROM projects INNER JOIN custom_values ON custom_values.customized_id = "
                "projects.id WHERE custom_field_id = 17 AND value = '1';")
    projects = cur.fetchall()
    context['projects'] = []
    total_required = 0
    for project in projects:
        cur.execute(
            "SELECT min(value), max(value) FROM custom_values WHERE customized_id = %(project)s "
            "AND (custom_field_id = 16 OR custom_field_id = 15);" % {
                'project': project[0]})
        dates = cur.fetchall()
        if len(dates) > 0 and dates[0][0] != '' and dates[0][1] != '' and dates[0][0] != dates[0][1]:
            start_date = str(dates[0][0])
            end_date = str(datetime.datetime.strptime(dates[0][1], '%Y-%m-%d') + datetime.timedelta(days=1))
        else:
            start_date = ''
            end_date = ''

        # get the required effort, if it exists
        cur.execute(
            "SELECT value FROM custom_values WHERE customized_id = %(project)s AND custom_field_id = 18;" % {
                'project': project[0]})
        effort = cur.fetchall()
        if len(effort) > 0:
            effort = effort[0][0]
        if effort == '':
            effort = 0
        else:
            effort = None

        if start_date != '' and datetime.datetime.strptime(start_date, '%Y-%m-%d').date() <= datetime.date.today() \
                <= datetime.datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S').date() and effort is not None:
            total_required += float(effort)

        context['projects'].append({
            'id': project[0],
            'name': project[1],
            'start': start_date,
            'end': end_date,
            'required_effort': effort,
            'prospect': False
        })

    cur.execute(
        "SELECT \"name\", start_date, end_date, fte_requirements, id FROM prospective_projects WHERE \"name\" "
        "NOT IN (SELECT DISTINCT(name) FROM projects);")
    prospects = cur.fetchall()
    for project in prospects:
        start_date = str(project[1])
        end_date = str(project[2])
        # for each, see if there's a start and end date
        if start_date != '' and datetime.datetime.strptime(start_date,
                                                           '%Y-%m-%d').date() <= datetime.date.today() \
                and end_date != '' and datetime.datetime.strptime(
                end_date, '%Y-%m-%d').date() >= datetime.date.today() and project[3] is not None:
            total_required += float(project[3])

        context['projects'].append({
            'id': project[4],
            'name': project[0],
            'start': start_date,
            'end': end_date,
            'required_effort': project[3],
            'prospect': True
        })

    context['total_required_for_today'] = total_required

    return render(request, 'planning.html', context)


@login_required
def get_all_dev_assignments(request):
    cur = connection.cursor()

    cur.execute(
        'SELECT users.firstname||\' \'||users.lastname, users.id, programmers.manager FROM users '
        'INNER JOIN programmers ON programmers.user_id = users.id WHERE programmers.active = TRUE '
        'ORDER BY users.lastname;')
    programmers = cur.fetchall()

    list = []
    for dev in programmers:
        # get their manager info
        cur.execute(
            "SELECT users.firstname||' '||users.lastname, users.id FROM users "
            "INNER JOIN programmers ON programmers.supervisor = users.id WHERE programmers.user_id = %(user)s;" % {
                'user': dev[1]})
        manager_info = cur.fetchone()

        # get their current assignment values as of today
        cur.execute(
            'SELECT SUM(percentage) FROM project_distribution WHERE "user" = %(user)s '
            'AND "from" <= CURRENT_DATE AND "to" >= CURRENT_DATE;' % {
                'user': dev[1]})
        current_assignment = cur.fetchone()[0]
        if current_assignment is None:
            current_assignment = 0
        if manager_info is None:
            manager_info = [None, None]
        new_entry = {
            'developer': dev[0],
            'developer_id': dev[1],
            'supervisor': dev[2],
            'manager_name': manager_info[0],
            'manager_id': manager_info[1],
            'today_assignment': (current_assignment * 100)
        }
        list.append(new_entry)

    # get a list of inactive users
    cur.execute(
        "select firstname||' '||lastname, id from users where id not in (select user_id "
        "from programmers where active = true) and login != '' order by lastname;")
    inactive_devs = cur.fetchall()

    # get a list of supervisors
    cur.execute(
        "select firstname||' '||lastname, users.id from users inner join programmers "
        "ON programmers.user_id = users.id WHERE programmers.manager = TRUE;")
    supervisors = cur.fetchall()

    context = {
        'inactive_devs': inactive_devs,
        'active_devs': list,
        'supervisors': supervisors
    }

    return HttpResponse(json.dumps(context))


@login_required
def get_assignments(request):
    cur = connection.cursor()

    if request.GET['prospect'] == 'true':
        cur.execute(
            "SELECT users.id, users.firstname, users.lastname, percentage, \"from\"::text, \"to\"::text, "
            "project_distribution.id FROM project_distribution INNER JOIN users "
            "ON users.id = project_distribution.user WHERE project_distribution.prospective_project = %(project)s;" % {
                'project': request.GET['project']})
    else:
        cur.execute(
            "SELECT users.id, users.firstname, users.lastname, percentage, \"from\"::text, \"to\"::text, "
            "project_distribution.id FROM project_distribution INNER JOIN users "
            "ON users.id = project_distribution.user WHERE project_distribution.project = %(project)s;" % {
                'project': request.GET['project']})
    distributions = cur.fetchall()

    # get the start/end date for the project
    if request.GET['prospect'] == 'true':
        cur.execute("SELECT start_date, end_date FROM prospective_projects WHERE id = %(project)s;" % {
            'project': request.GET['project']})
    else:
        cur.execute(
            "SELECT min(value::date), max(value::date) FROM custom_values "
            "WHERE customized_id = %(project)s AND (custom_field_id = 16 OR custom_field_id = 15);" % {
                'project': request.GET['project']})
    dates = cur.fetchall()
    if len(dates) > 0 and dates[0][0] is not None and dates[0][1] is not None:
        start_date = str(dates[0][0])
        end_date = str(dates[0][1])
    else:
        start_date = ''
        end_date = ''

    # get the required effort, if it exists
    if request.GET['prospect'] == 'true':
        cur.execute("SELECT fte_requirements FROM prospective_projects WHERE id = %(project)s;" % {
            'project': request.GET['project']})
    else:
        cur.execute("SELECT value FROM custom_values WHERE customized_id = %(project)s AND custom_field_id = 18;" % {
            'project': request.GET['project']})
    effort = cur.fetchall()
    if len(effort) > 0:
        effort = effort[0]
    else:
        effort = None

    # get active developers
    if request.GET['prospect'] == 'true':
        cur.execute(
            "SELECT users.firstname||' '||users.lastname, users.id FROM users "
            "INNER JOIN programmers ON programmers.user_id = users.id WHERE programmers.active = TRUE;" % {
                'project': request.GET['project']})
    else:
        cur.execute(
            "SELECT users.firstname||' '||users.lastname, users.id FROM users "
            "INNER JOIN programmers ON programmers.user_id = users.id WHERE programmers.active = TRUE;" % {
                'project': request.GET['project']})
    programmers = cur.fetchall()

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'assignees': distributions,
        'developers': programmers,
        'required_effort': effort
    }

    return HttpResponse(json.dumps(context))


@login_required
def get_planning_projection(request):
    cur = connection.cursor()

    project_id = request.GET['project']

    # get project budget
    cur.execute("select value from custom_values where custom_field_id = 12 and customized_id = %(project)s;" % {
        'project': project_id})
    budget = cur.fetchone()[0]

    future_spending_hours = 0

    # get the current internal rate
    cur.execute(
        "SELECT rate FROM charge_rates WHERE internal = TRUE AND category = 'Programming' "
        "and start_date <= CURRENT_DATE and end_date >= CURRENT_DATE LIMIT 1;")
    rate = cur.fetchone()[0]

    # get a list of developers assigned to this project
    cur.execute(
        'SELECT "user", percentage, GREATEST("from", CURRENT_DATE), "to", manager '
        'FROM project_distribution INNER JOIN programmers ON programmers.user_id = project_distribution.user '
        'WHERE project = %(project)s AND "to" > CURRENT_DATE ;' % {
            'project': project_id})
    developers = cur.fetchall()

    for dev in developers:
        current_date_iterator = dev[2]  # datetime.datetime.strptime(dev[2], '%Y-%m-%d').date()
        end_date = dev[3]  # datetime.datetime.strptime(dev[3], '%Y-%m-%d').date()

        while current_date_iterator <= end_date:
            if dev[4] is True:
                future_spending_hours += float(manager_date_working_hours(current_date_iterator) * float(dev[1]))
            else:
                future_spending_hours += float(date_working_hours(current_date_iterator) * float(dev[1]))
            current_date_iterator = current_date_iterator + datetime.timedelta(days=1)

    future_spending_cost = future_spending_hours * float(rate)

    # how much have we spent so far?
    cur.execute("select value from custom_values where custom_field_id = 13 and customized_id = %(project)s;" % {
        'project': project_id})
    spent = cur.fetchone()[0]

    total_projected_spending = float(spent) + float(future_spending_cost)

    context = {
        'planned_spending': "%.2f" % round(total_projected_spending, 2),
        'project_budget': budget
    }
    return HttpResponse(json.dumps(context))


@login_required
def developer_assignments(request):
    cur = connection.cursor()

    dev_id = request.GET['dev_id']

    # get their distributions
    cur.execute(
        'SELECT projects.name, projects.id, (percentage * 100)::text, "from", "to", '
        'project_distribution.id, \'\'::text FROM project_distribution INNER JOIN projects '
        'ON projects.id = project_distribution.project WHERE "user" = %(user)s ORDER BY "from";' % {
            'user': dev_id})
    assignments = cur.fetchall()

    assignment_list = []
    for assignment in assignments:
        new_assignment = {
            'project_id': assignment[1],
            'project': assignment[0],
            'effort': assignment[2],
            'start': str(assignment[3]),
            'end': str(assignment[4] + datetime.timedelta(days=1)),
            'entry_id': assignment[5],
            'class': assignment[6]
        }
        assignment_list.append(new_assignment)

    # get their manager info
    cur.execute(
        "SELECT users.firstname||' '||users.lastname, users.id FROM users "
        "INNER JOIN programmers ON programmers.supervisor = users.id WHERE programmers.user_id = %(user)s;" % {
            'user': dev_id})
    manager_info = cur.fetchone()
    if manager_info is None:
        manager_info = [None, None]

    context = {
        'assignments': assignment_list,
        'manager_name': manager_info[0],
        'manager_id': manager_info[1],
        'developer_id': dev_id
    }

    return HttpResponse(json.dumps(context))


@login_required
def deactivate(request):
    cur = connection.cursor()

    cur.execute("UPDATE programmers SET active = FALSE WHERE user_id = %(id)s;" % {'id': request.GET['id']})
    connection.commit()

    return HttpResponse('200')


@login_required
def activate(request):
    cur = connection.cursor()

    cur.execute("SELECT COUNT(*) FROM programmers WHERE user_id = %(id)s;" % {'id': request.GET['id']})
    count = cur.fetchone()[0]
    if count == 0:
        cur.execute("INSERT INTO programmers (user_id, active) VALUES (%(user)s, TRUE);" % {'user': request.GET['id']})
    else:
        cur.execute("UPDATE programmers SET active = TRUE WHERE user_id = %(id)s;" % {'id': request.GET['id']})
    connection.commit()

    return HttpResponse('200')


@login_required
def update_supervisor(request):
    cur = connection.cursor()

    # should we remove the supervisor?
    if request.GET['man_id'] == 'None':
        supervisor_id = 'NULL'
    else:
        supervisor_id = request.GET['man_id']

    cur.execute("UPDATE programmers SET supervisor = %(supervisor)s WHERE user_id = %(id)s;" % {
        'id': request.GET['id'], 'supervisor': supervisor_id})
    connection.commit()

    return HttpResponse('200')


@login_required
def remove_assignment(request):
    cur = connection.cursor()

    cur.execute("DELETE FROM project_distribution WHERE id = %(id)s;" % {'id': request.GET['entry_id']})
    connection.commit()

    return HttpResponse('200')


@login_required
def add_assignment(request):
    cur = connection.cursor()

    if 'new_' in request.GET['project']:
        cur.execute(
            "INSERT INTO project_distribution (\"user\", prospective_project, percentage, \"from\", \"to\")"
            " VALUES (%(user)s, %(project)s, %(percent)s, '%(from)s'::date, '%(to)s'::date) RETURNING id;" % {
                'user': request.GET['developer'], 'project': request.GET['project'].replace('new_', ''),
                'percent': request.GET['effort'], 'from': request.GET['start'], 'to': request.GET['end']})
    else:
        cur.execute(
            "INSERT INTO project_distribution (\"user\", project, percentage, \"from\", \"to\") "
            "VALUES (%(user)s, %(project)s, %(percent)s, '%(from)s'::date, '%(to)s'::date) RETURNING id;" % {
                'user': request.GET['developer'], 'project': request.GET['project'], 'percent': request.GET['effort'],
                'from': request.GET['start'], 'to': request.GET['end']})
    connection.commit()

    return HttpResponse('200')
