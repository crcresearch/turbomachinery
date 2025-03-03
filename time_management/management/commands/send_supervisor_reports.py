from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone
from django.db import connection
from django.core.mail import send_mail
from datetime import datetime, timedelta, date
from time_management.models import RedmineUser, TimeEntry, Project, Team, TeamMember
from django.contrib.auth.models import User
import logging
import html2text
import smtplib
from email.mime.text import MIMEText
import psycopg2

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generates weekly/monthly time reports for Supervisors'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test_email',
            type=str,
            help='Send all reports to this test email address',
        )
        parser.add_argument(
            '--print',
            action='store_true',
            help='Print reports to console instead of sending emails',
        )
        parser.add_argument(
            '--monthly',
            action='store_true',
            help='Generate monthly report instead of weekly',
        )
        # Add date arguments
        parser.add_argument(
            '--start_date',
            type=str,
            help='Start date (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--end_date',
            type=str,
            help='End date (YYYY-MM-DD)',
        )

    def get_report_dates(self, monthly=False, options=None):
        """Get start and end dates for the report period."""
        # Check for explicit dates first
        if options and options.get('start_date') and options.get('end_date'):
            return (
                datetime.strptime(options['start_date'], '%Y-%m-%d').date(),
                datetime.strptime(options['end_date'], '%Y-%m-%d').date()
            )
        
        today = timezone.now().date()
        
        # Only bypass day check if explicitly testing
        if options and (options.get('print') or options.get('test_email')):
            if monthly:
                start_date = today.replace(day=1)
                end_date = today
            else:
                # Get previous week (Saturday through Friday)
                end_date = today - timedelta(days=(today.weekday() + 3) % 7)  # Previous Friday
                start_date = end_date - timedelta(days=6)  # Previous Saturday
            return start_date, end_date
        
        # Production checks - no bypass
        if monthly and today.weekday() == 4:  # If it's Friday
            # Check if it's the last Friday of the month
            next_week = today + timedelta(days=7)
            if next_week.month != today.month:
                # Get first day of the month
                start_date = today.replace(day=1)
                # End date is today
                end_date = today
                return start_date, end_date
            return None, None  # Not the last Friday
        
        elif not monthly and today.weekday() == 0:  # If it's Monday
            # Get previous week (Saturday through Friday)
            end_date = today - timedelta(days=3)  # Previous Friday
            start_date = end_date - timedelta(days=6)  # Previous Saturday
            return start_date, end_date
        
        return None, None  # Not Monday or last Friday

    def send_notification(self, to_email, message_body, message_subject):
        msg = MIMEText(message_body, 'html')
        msg['Subject'] = message_subject
        msg['From'] = 'noreply@turbo.crc.nd.edu'
        msg['To'] = to_email
        list_of_recipients = [to_email]

        s = smtplib.SMTP('dockerhost')
        s.sendmail('noreply@turbo.crc.nd.edu', list_of_recipients, msg.as_string())
        s.quit()

    def handle(self, *args, **options):
        print("\n=== Starting Supervisor Report Generation ===")
        
        start_date, end_date = self.get_report_dates(options.get('monthly', False), options)
        print("\nDate Range: %s to %s" % (start_date, end_date))
        
        try:
            connection = psycopg2.connect(host='database1', database='redmine', user='postgres', password="Let's go turbo!")
            cursor = connection.cursor()
            
            # Get all supervisors
            cursor.execute("""
                SELECT DISTINCT cv.value 
                FROM custom_values cv 
                JOIN custom_fields cf ON cf.id = cv.custom_field_id 
                WHERE cf.name = 'Supervisor Notification Emails'
                AND cv.value IS NOT NULL 
                AND cv.value != ''
                ORDER BY cv.value;
            """)
            supervisors = cursor.fetchall()
            print("\nFound %d supervisors" % len(supervisors))
            
            for supervisor in supervisors:
                supervisor_email = supervisor[0]
                print("\nProcessing supervisor: %s" % supervisor_email)
                
                # Get team members for this supervisor
                cursor.execute("""
                    SELECT u.id 
                    FROM users u
                    JOIN custom_values cv ON cv.customized_id = u.id
                    JOIN custom_fields cf ON cf.id = cv.custom_field_id
                    WHERE cf.name = 'Supervisor Notification Emails'
                    AND cv.value = %s;
                """, [supervisor_email])
                team_members = [row[0] for row in cursor.fetchall()]
                
                if team_members:
                    # Get entries using Django ORM
                    entries = TimeEntry.objects.filter(
                        user_id__in=team_members,
                        spent_on__range=[start_date, end_date]
                    ).select_related('user', 'project', 'activity')
                    
                    # Generate report data
                    report_data = {}
                    for entry in entries:
                        username = '%s %s' % (entry.user.firstname, entry.user.lastname)
                        if username not in report_data:
                            report_data[username] = {
                                'total_hours': 0.0,
                                'projects': {}
                            }
                        
                        project_code = entry.project.identifier
                        if project_code not in report_data[username]['projects']:
                            report_data[username]['projects'][project_code] = {
                                'hours': 0.0,
                                'activities': {},
                                'dates': set()
                            }
                        
                        activity = entry.comments or (entry.activity.name if entry.activity else '')
                        if activity:
                            if activity not in report_data[username]['projects'][project_code]['activities']:
                                report_data[username]['projects'][project_code]['activities'][activity] = {
                                    'hours': 0.0,
                                    'dates': set()
                                }
                            report_data[username]['projects'][project_code]['activities'][activity]['hours'] += float(entry.hours)
                            report_data[username]['projects'][project_code]['activities'][activity]['dates'].add(entry.spent_on)
                        
                        report_data[username]['projects'][project_code]['hours'] += float(entry.hours)
                        report_data[username]['total_hours'] += float(entry.hours)
                        report_data[username]['projects'][project_code]['dates'].add(entry.spent_on)
                    
                    # Convert dates to strings
                    for username in report_data:
                        for project in report_data[username]['projects']:
                            dates = sorted(report_data[username]['projects'][project]['dates'])
                            report_data[username]['projects'][project]['date_str'] = ', '.join(d.strftime('%m/%d') for d in dates)
                            for activity in report_data[username]['projects'][project]['activities']:
                                act_dates = sorted(report_data[username]['projects'][project]['activities'][activity]['dates'])
                                report_data[username]['projects'][project]['activities'][activity]['date_str'] = ', '.join(d.strftime('%m/%d') for d in act_dates)
                    
                    # Generate HTML content
                    template_name = 'emails/supervisor_monthly.html' if options.get('monthly') else 'emails/supervisor_weekly.html'
                    
                    if options.get('monthly'):
                        # Group entries by week
                        weekly_data = {}
                        for entry in entries:
                            # Get the Monday of the week
                            week_start = entry.spent_on - timedelta(days=entry.spent_on.weekday())
                            if week_start not in weekly_data:
                                weekly_data[week_start] = {}
                            username = '%s %s' % (entry.user.firstname, entry.user.lastname)
                            if username not in weekly_data[week_start]:
                                weekly_data[week_start][username] = {
                                    'total_hours': 0.0,
                                    'projects': {}
                                }
                            project_code = entry.project.identifier
                            if project_code not in weekly_data[week_start][username]['projects']:
                                weekly_data[week_start][username]['projects'][project_code] = {
                                    'hours': 0.0,
                                    'activities': {},
                                    'dates': set()
                                }
                            activity = entry.comments or (entry.activity.name if entry.activity else '')
                            if activity:
                                if activity not in weekly_data[week_start][username]['projects'][project_code]['activities']:
                                    weekly_data[week_start][username]['projects'][project_code]['activities'][activity] = {
                                        'hours': 0.0,
                                        'dates': set()
                                    }
                                weekly_data[week_start][username]['projects'][project_code]['activities'][activity]['hours'] += float(entry.hours)
                                weekly_data[week_start][username]['projects'][project_code]['activities'][activity]['dates'].add(entry.spent_on)
                            weekly_data[week_start][username]['projects'][project_code]['hours'] += float(entry.hours)
                            weekly_data[week_start][username]['total_hours'] += float(entry.hours)
                            weekly_data[week_start][username]['projects'][project_code]['dates'].add(entry.spent_on)
                        
                        # Sort weeks and generate final data
                        sorted_weeks = sorted(weekly_data.keys())
                        context = {
                            'supervisor_name': supervisor_email,
                            'start_date': start_date,
                            'end_date': end_date,
                            'entries': [
                                {'week_start': week, 'data': weekly_data[week]}
                                for week in sorted_weeks
                            ]
                        }
                    else:
                        # Weekly report context
                        context = {
                            'supervisor_name': supervisor_email,
                            'start_date': start_date,
                            'end_date': end_date,
                            'report_data': report_data
                        }
                    
                    html_content = render_to_string(template_name, context)
                    
                    if options.get('print'):
                        print("\nReport Content:")
                        print(html_content)
                    else:
                        self.send_notification(
                            options.get('test_email', supervisor_email),
                            html_content,
                            'NDTL Program %s Time Report (%s - %s)' % (
                                'Monthly' if options.get('monthly') else 'Weekly',
                                start_date.strftime('%b %d'),
                                end_date.strftime('%b %d')
                            )
                        )
                        print("Sent report to %s" % supervisor_email)
            
        except Exception as e:
            print("ERROR: %s" % str(e))
            raise
        
        print("\n=== Supervisor Report Generation Complete ===\n") 