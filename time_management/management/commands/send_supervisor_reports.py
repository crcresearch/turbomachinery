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
import time
from email.mime.multipart import MIMEMultipart

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
        msg = MIMEMultipart()
        msg['From'] = 'noreply@turbo.crc.nd.edu'
        msg['To'] = to_email
        msg['Subject'] = message_subject
        msg.attach(MIMEText(message_body, 'html'))

        try:
            smtp = smtplib.SMTP('dockerhost')
            smtp.sendmail('noreply@turbo.crc.nd.edu', to_email, msg.as_string())
            smtp.close()
            time.sleep(15)  # Wait 15 seconds between emails to stay under rate limit
            return True
        except Exception as e:
            print("Error sending email to %s: %s" % (to_email, str(e)))
            return False

    def send_supervisor_report(self, supervisor_email, start_date, end_date, options, team_members):
        print("\nProcessing supervisor:", supervisor_email)
        
        # If test_email is set, use that instead of actual supervisor email
        to_email = options.get('test_email', supervisor_email)
        
        # For monthly reports, break into weeks
        weekly_ranges = []
        if options.get('monthly'):
            current = start_date
            while current <= end_date:
                # Find Saturday (start of week)
                week_start = current - timedelta(days=current.weekday() + 2)
                if week_start < start_date:
                    week_start = start_date
                    
                # Find Friday (end of week)
                week_end = week_start + timedelta(days=6)
                if week_end > end_date:
                    week_end = end_date
                
                # Get entries for this week
                entries = TimeEntry.objects.filter(
                    spent_on__range=[week_start, week_end],
                    user_id__in=team_members
                ).select_related('user', 'project', 'activity')
                
                # Process entries into report data
                report_data = self.process_entries(entries)
                
                weekly_ranges.append({
                    'start': week_start,
                    'end': week_end,
                    'entries': report_data
                })
                
                current = week_end + timedelta(days=1)
        else:
            # Single week processing
            entries = TimeEntry.objects.filter(
                spent_on__range=[start_date, end_date],
                user_id__in=team_members
            ).select_related('user', 'project', 'activity')
            
            report_data = self.process_entries(entries)
            
            weekly_ranges = [{
                'start': start_date,
                'end': end_date,
                'entries': report_data
            }]
        
        # Generate the report content
        template = get_template('notification_emails/supervisor_monthly_report.html')
        message = template.render({
            'supervisor_name': supervisor_email,
            'start_date': start_date,
            'end_date': end_date,
            'weekly_ranges': weekly_ranges
        })
        
        # Send the email and check result
        if self.send_notification(to_email, message, 'Turbomachinery Lab Monthly Hours Report'):
            print("Sent report to", to_email)
        else:
            print("Failed to send report to", to_email)
            # Sleep here to give SMTP server time to recover
            time.sleep(15)

    def process_entries(self, entries):
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
        
        return report_data

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
                    self.send_supervisor_report(
                        supervisor_email,
                        start_date,
                        end_date,
                        options,
                        team_members
                    )
            
        except Exception as e:
            print("ERROR: %s" % str(e))
            raise
        
        print("\n=== Supervisor Report Generation Complete ===\n") 