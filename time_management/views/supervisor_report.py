from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from time_management.models import RedmineUser, TimeEntry, Project, Team, TeamMember
from datetime import datetime, timedelta
from django.db import connection
from django.contrib.auth.models import User

@login_required
def supervisor_weekly_report(request):
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    
    if request.GET.get('start_date'):
        start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d').date()
    if request.GET.get('end_date'):
        end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d').date()

    # Get all supervisors
    supervisors = Team.objects.all().select_related('manager')
    all_reports = {}

    for supervisor in supervisors:
        # Get auth user email
        try:
            auth_user = User.objects.get(username=supervisor.manager.login)
            email = auth_user.email
        except User.DoesNotExist:
            email = supervisor.manager.login

        # Get team members excluding the supervisor
        team_members = TeamMember.objects.filter(
            team=supervisor
        ).exclude(
            member_id=supervisor.manager.id
        ).values_list('member_id', flat=True)

        entries = TimeEntry.objects.filter(
            user_id__in=team_members,
            spent_on__range=[start_date, end_date]
        ).values(
            'user__firstname',
            'user__lastname',
            'project__identifier',
            'comments',
            'hours',
            'activity__name',
            'user_id',
            'spent_on'
        ).order_by('user__firstname', 'user__lastname', 'project__identifier')

        report_data = {}

        # First group by user and category
        for entry in entries:
            username = '{} {}'.format(entry['user__firstname'], entry['user__lastname'])
            
            if username not in report_data:
                report_data[username] = {
                    'total_hours': 0.0,
                    'projects': {}
                }
            
            project_code = entry['project__identifier']
            activity = entry['comments'] or entry['activity__name']
            hours = float(entry['hours']) if entry['hours'] else 0.0
            spent_on = entry['spent_on'].strftime('%Y-%m-%d')

            # Add project if it doesn't exist
            if project_code not in report_data[username]['projects']:
                report_data[username]['projects'][project_code] = {
                    'hours': hours,
                    'dates': {spent_on: hours},
                    'activities': {}
                }
            else:
                report_data[username]['projects'][project_code]['hours'] += hours
                if spent_on in report_data[username]['projects'][project_code]['dates']:
                    report_data[username]['projects'][project_code]['dates'][spent_on] += hours
                else:
                    report_data[username]['projects'][project_code]['dates'][spent_on] = hours

            # Add activity under project
            if activity and activity != project_code:
                if activity not in report_data[username]['projects'][project_code]['activities']:
                    report_data[username]['projects'][project_code]['activities'][activity] = {
                        'hours': hours,
                        'dates': {spent_on: hours}
                    }
                else:
                    act_data = report_data[username]['projects'][project_code]['activities'][activity]
                    act_data['hours'] += hours
                    if spent_on in act_data['dates']:
                        act_data['dates'][spent_on] += hours
                    else:
                        act_data['dates'][spent_on] = hours

            # Update user total
            report_data[username]['total_hours'] += hours

        # Format date strings
        for username, user_data in report_data.items():
            for project_code, project_data in user_data['projects'].items():
                date_parts = []
                for date, hours in sorted(project_data['dates'].items()):
                    date_parts.append('{}: {}'.format(date, hours))
                project_data['date_str'] = ', '.join(date_parts)
                
                for activity, activity_data in project_data['activities'].items():
                    date_parts = []
                    for date, hours in sorted(activity_data['dates'].items()):
                        date_parts.append('{}: {}'.format(date, hours))
                    activity_data['date_str'] = ', '.join(date_parts)

        if report_data:
            supervisor_name = '{} {} ({})'.format(
                supervisor.manager.firstname,
                supervisor.manager.lastname,
                email
            )
            all_reports[supervisor_name] = report_data

    week_number = start_date.isocalendar()[1]
    
    context = {
        'all_reports': all_reports,
        'start_date': start_date,
        'end_date': end_date,
        'week_number': week_number,
    }

    return render(request, 'reports/supervisor_weekly.html', context)