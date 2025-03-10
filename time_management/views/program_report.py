from django.shortcuts import render
from django.db.models import Sum
from django.utils import timezone
from django.db import connection
from datetime import datetime, timedelta, date
from time_management.models import TimeEntry

def get_week_number(date_obj):
    """Get the week number (1-52) for the given date."""
    return (date_obj.timetuple().tm_yday - 1) // 7 + 1

def get_last_two_weeks():
    """Get start and end dates for the last two complete weeks."""
    today = timezone.now().date()
    # Find the most recent Sunday
    end_date = today - timedelta(days=(today.weekday() + 1))
    # Go back two weeks for the start date
    start_date = end_date - timedelta(days=30)
    return start_date, end_date

def program_weekly_report(request):
    # Get date from request or use last two weeks
    date_str = request.GET.get('date')
    if date_str:
        try:
            current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            weekday = current_date.weekday()
            start_date = current_date - timedelta(days=weekday)
            end_date = start_date + timedelta(days=13)
        except ValueError:
            start_date, end_date = get_last_two_weeks()
    else:
        start_date, end_date = get_last_two_weeks()

    # Calculate week numbers for both weeks
    week_number_start = str(get_week_number(start_date)).zfill(2)
    week_number_end = str(get_week_number(start_date + timedelta(days=7))).zfill(2)
    week_display = "%s-%s" % (week_number_start, week_number_end)

    print "DEBUG: Using dates: %s to %s Weeks %s" % (start_date, end_date, week_display)

    # Get Financial PIs first
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT p.identifier, cv.value as financial_pi
            FROM projects p
            LEFT JOIN custom_values cv ON cv.customized_id = p.id
            LEFT JOIN custom_fields cf ON cf.id = cv.custom_field_id
            WHERE cf.name = 'Financial PI'
        """)
        financial_pis = dict(cursor.fetchall())

    # Get time entries using Django ORM
    entries = TimeEntry.objects.filter(
        spent_on__range=[start_date, end_date],
        hours__gt=0
    ).select_related(
        'project',
        'user',
        'activity'
    ).order_by(
        'project__identifier',
        'user__lastname',
        'user__firstname'
    )

    print "DEBUG: Found %d entries" % entries.count()

    # Check earliest and latest entries in system
    earliest = TimeEntry.objects.filter(hours__gt=0).order_by('spent_on').first()
    latest = TimeEntry.objects.filter(hours__gt=0).order_by('-spent_on').first()
    print "DEBUG: Earliest entry:", earliest.spent_on if earliest else None
    print "DEBUG: Latest entry:", latest.spent_on if latest else None

    # Initialize reports dictionary grouped by Financial PI
    pi_reports = {}
    
    for entry in entries:
        project_code = entry.project.identifier
        username = '%s %s' % (entry.user.firstname, entry.user.lastname)
        activity = entry.comments or (entry.activity.name if entry.activity else '')
        hours = float(entry.hours) if entry.hours else 0.0
        financial_pi = financial_pis.get(project_code, 'Unassigned')

        print "DEBUG: Processing entry:", project_code, username, hours

        # Initialize financial PI if it doesn't exist
        if financial_pi not in pi_reports:
            pi_reports[financial_pi] = {
                'total_hours': 0.0,
                'projects': {}
            }

        # Initialize project if it doesn't exist
        if project_code not in pi_reports[financial_pi]['projects']:
            pi_reports[financial_pi]['projects'][project_code] = {
                'total_hours': 0.0,
                'users': {}
            }

        # Initialize user if they don't exist in this project
        if username not in pi_reports[financial_pi]['projects'][project_code]['users']:
            pi_reports[financial_pi]['projects'][project_code]['users'][username] = {
                'hours': 0.0,
                'activities': {}
            }

        # Add activity
        if activity:
            if activity not in pi_reports[financial_pi]['projects'][project_code]['users'][username]['activities']:
                pi_reports[financial_pi]['projects'][project_code]['users'][username]['activities'][activity] = {
                    'hours': hours
                }
            else:
                pi_reports[financial_pi]['projects'][project_code]['users'][username]['activities'][activity]['hours'] += hours

        # Update totals
        pi_reports[financial_pi]['projects'][project_code]['users'][username]['hours'] += hours
        pi_reports[financial_pi]['projects'][project_code]['total_hours'] += hours
        pi_reports[financial_pi]['total_hours'] += hours

    print "DEBUG: Final structure has %d projects" % len(pi_reports)

    # Sort by Financial PI
    pi_reports = dict(sorted(pi_reports.items()))
    
    # Sort projects within each Financial PI
    for pi_data in pi_reports.values():
        pi_data['projects'] = dict(sorted(pi_data['projects'].items()))

    # Previous and next two-week period links
    prev_date = start_date - timedelta(days=14)
    next_date = start_date + timedelta(days=14)

    context = {
        'pi_reports': pi_reports,
        'week_number': week_display,
        'start_date': start_date.strftime('%b. %d, %Y'),
        'end_date': end_date.strftime('%b. %d, %Y'),
        'prev_week': prev_date.strftime('%Y-%m-%d'),
        'next_week': next_date.strftime('%Y-%m-%d'),
        'current_date': timezone.now().strftime('%Y-%m-%d')
    }

    return render(request, 'reports/program_weekly.html', context) 