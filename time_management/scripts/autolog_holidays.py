#!/usr/bin/env python
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from holidays import get_holidays
import datetime
import psycopg2


def log_holiday(date, name):
    print "Connecting..."
    connection = psycopg2.connect(
        host=os.environ.get('POSTGRES_HOST'),
        user=os.environ.get('POSTGRES_USER'),
        password=os.environ.get('POSTGRES_PASSWORD'),
        database=os.environ.get('POSTGRES_DB')
    )
    cursor = connection.cursor()
    # get the project ID for "University Holidays"
    cursor.execute("SELECT id FROM projects WHERE name= 'University Holidays';")
    project_id = cursor.fetchone()[0]

    # get a list of users we need to log time for
    cursor.execute("SELECT user_id FROM members WHERE project_id = %(id)s;" % {'id': project_id})
    members = cursor.fetchall()

    for member in members:
        cursor.execute("INSERT INTO time_entries (project_id, user_id, hours, comments, activity_id, spent_on, tyear, "
                       "tmonth, tweek, created_on, updated_on) VALUES (%(project_id)s, %(user_id)s, 8, "
                       "'%(holiday_name)s', 98, '%(date)s'::date, %(year)s, %(month)s, %(week)s, now(), now());" % {
            'project_id': project_id,
            'user_id': member[0],
            'holiday_name': name,
            'date': date.strftime('%Y-%m-%d'),
            'year': date.strftime('%Y'),
            'month': date.strftime('%m'),
            'week': (((datetime.datetime.combine(date, datetime.datetime.min.time()) - datetime.datetime(date.year,1,1)).days // 7) + 1)
        })
    connection.commit()


if __name__ == '__main__':

    holidays = get_holidays(datetime.datetime.now().year)

    # check if a specific holiday was given
    found = False
    if len(sys.argv) > 1:
        possible_holidays = []
        target_holiday = sys.argv[1]
        for holiday in holidays:
            if "'"+holiday['name']+"'" not in possible_holidays:
                possible_holidays.append("'"+holiday['name']+"'")
            if target_holiday == holiday['name']:
                found = True
                log_holiday(holiday['date'], holiday['name'])
        if not found:
            print("Failed to find matching holiday.  Holiday name should match one of the following:")
            for holiday in possible_holidays:
                print(holiday)

    else:
        for date in holidays:
            if datetime.datetime.now().date() == date['date']:
                print "Logging time for:", date['name']
                log_holiday(date['date'], date['name'])