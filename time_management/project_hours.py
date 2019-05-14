from django.shortcuts import render, HttpResponse
import datetime
import json

from django.db import connection


def project_hours_page(request):
    cursor = connection.cursor()
    cursor.execute("SELECT id, name FROM projects WHERE status = 1 ORDER BY name;")

    project_list = []
    for p in cursor.fetchall():
        project_list.append({
            'name': p[1],
            'id': p[0]
        })

    # get a default list of users for the first project
    cursor.execute("SELECT users.id, firstname, lastname "
                   "FROM users "
                   "INNER JOIN members ON members.user_id = users.id "
                   "WHERE members.project_id = %(proj)s;" % {
        'proj': project_list[0]['id']
    })

    user_list = []
    for user in cursor.fetchall():
        user_list.append({
            'id': user[0],
            'name': user[1] + ' ' + user[2]
        })

    return render(request, 'project_hours.html', {
        'projects': project_list,
        'start': (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%m/%d/%Y'),
        'end': datetime.datetime.now().strftime('%m/%d/%Y'),
        'users': user_list
    })

def generate_turbo_weeks(start_date, end_date):
    """
    Given a date range (start_date and end_date), generate a list of weeks where each item in the list has a start
    and end date that defines itself as a week.  These weeks have the first day of the week on Saturday and the last
    day of the week the following Friday.

    Note: If the start or end date does not fall on a Saturay or Friday (respectively), the "start" or "end" of the
    first or last list item will only include those dates (you won't get dates in there that are outside of the
    supplied range).
    :param start_date:
    :param end_date:
    :return:
    """
    week_list = []
    current_date = start_date

    current_week = {
        'start': current_date,
        'end': None
    }

    while current_date <= end_date:
        # are we ending this week?
        if current_date.weekday() == 4:
            current_week['end'] = current_date
            week_list.append(current_week)

        # are we starting a new week?
        if current_date.weekday() == 5:
            current_week = {
                'start': current_date,
                'end': None
            }

        current_date = current_date + datetime.timedelta(days=1)

    # make sure to end off our current week
    if current_week['end'] is None:
        current_week['end'] = end_date
        week_list.append(current_week)

    return week_list


def get_project_hours(request):
    user_list = request.GET.getlist('users[]')
    start = datetime.datetime.strptime(request.GET['start'], '%m/%d/%Y')
    end = datetime.datetime.strptime(request.GET['end'], '%m/%d/%Y')
    project = request.GET['project']

    cursor = connection.cursor()

    week_list = generate_turbo_weeks(start, end)

    users = []

    for user in user_list:
        user_data = {
            'id': user,
            'data': []
        }

        # grab this users name
        cursor.execute("SELECT firstname, lastname FROM users "
                       "WHERE id = %(user)s;" % {
            'user': user
        })
        name = cursor.fetchone()
        user_data['name'] = name[0] + ' ' + name[1]

        # for each week, get a sum of hours for each user and the given project
        for week in week_list:
            cursor.execute("SELECT SUM(hours) FROM time_entries "
                           "WHERE user_id = %(user)s "
                           "AND project_id = %(project)s "
                           "AND spent_on >= '%(start)s' "
                           "AND spent_on <= '%(end)s';" % {
                'user': user,
                'project': project,
                'start': week['start'].strftime('%Y-%m-%d'),
                'end': week['end'].strftime('%Y-%m-%d')
            })

            hours = cursor.fetchone()[0]
            if hours is None:
                hours = 0
            user_data['data'].append(hours)

        users.append(user_data)

    return_data = {
        'series': users,
        'weeks': []
    }
    for week in week_list:
        if week['start'] != week['end']:
            return_data['weeks'].append(
                week['start'].strftime('%m/%d/%Y') + ' - ' + week['start'].strftime('%m/%d/%Y')
            )
        else:
            return_data['weeks'].append(
                week['start'].strftime('%m/%d/%Y')
            )

    return HttpResponse(json.dumps(return_data))


def get_users_for_project(request):
    cursor = connection.cursor()

    # get a default list of users for the first project
    cursor.execute("SELECT users.id, firstname, lastname "
                   "FROM users "
                   "INNER JOIN members ON members.user_id = users.id "
                   "WHERE members.project_id = %(proj)s;" % {
                       'proj': request.GET['project']
                   })

    user_list = []
    for user in cursor.fetchall():
        user_list.append({
            'id': user[0],
            'name': user[1] + ' ' + user[2]
        })

    return render(request, 'project_user_list.html', {'users': user_list})
