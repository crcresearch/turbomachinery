from django.core.management.base import BaseCommand
from django.template.loader import get_template, render_to_string
from django.utils import timezone
from django.db import connection
from django.core.mail import send_mail
from datetime import datetime, timedelta, date
from time_management.models import TimeEntry, RedmineUser, Project
import logging
import html2text
import re
import smtplib
from email.mime.text import MIMEText
import psycopg2
import time
import os
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generates weekly/monthly time reports for PIs (includes users with zero hours)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test_email',
            type=str,
            help='Send all reports to this test email address'
        )
        parser.add_argument(
            '--print',
            action='store_true',
            help='Print reports to console instead of sending emails',
        )
        parser.add_argument(
            '--monthly',
            action='store_true',
            help='Generate monthly report instead of weekly'
        )
        parser.add_argument(
            '--start_date',
            type=str,
            help='Start date (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--end_date',
            type=str,
            help='End date (YYYY-MM-DD)'
        )

    def is_email(self, string):
        """Check if string is an email address."""
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_regex, string) is not None

    def get_report_dates(self, monthly=False, options=None):
        """Get start and end dates for the report period."""
        # Check for explicit dates first
        if options and options.get('start_date') and options.get('end_date'):
            return (
                datetime.strptime(options['start_date'], '%Y-%m-%d').date(),
                datetime.strptime(options['end_date'], '%Y-%m-%d').date()
            )
        
        today = timezone.now().date()
        
        if monthly:
            # Find the last Friday of current month
            current_month_end = today.replace(day=1) + timedelta(days=32)  # Go to next month
            current_month_end = current_month_end.replace(day=1) - timedelta(days=1)  # Back to last day
            
            last_friday = current_month_end
            while last_friday.weekday() != 4:  # 4 is Friday
                last_friday -= timedelta(days=1)
            
            if today == last_friday:
                # Find the last Friday of previous month
                prev_month_end = today.replace(day=1) - timedelta(days=1)
                prev_last_friday = prev_month_end
                while prev_last_friday.weekday() != 4:
                    prev_last_friday -= timedelta(days=1)
                
                # Start from day AFTER the previous last Friday
                start_date = prev_last_friday + timedelta(days=1)
                end_date = last_friday
                return start_date, end_date
        else:
            # Weekly report: Running on Monday, covering previous Sat-Fri
            if today.weekday() == 0:  # Monday
                end_date = today - timedelta(days=3)  # Previous Friday
                start_date = end_date - timedelta(days=6)  # Previous Saturday
            else:
                # If running on a different day, still maintain Sat-Fri pattern
                days_after_friday = (today.weekday() - 4) % 7
                end_date = today - timedelta(days=days_after_friday)  # Most recent Friday
                start_date = end_date - timedelta(days=6)  # Saturday before that
            
            return start_date, end_date

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
            time.sleep(120)  # Wait 2 minutes between emails
            return True
            
        except smtplib.SMTPConnectError as e:
            if "Connection rate limit exceeded" in str(e):
                self.stdout.write(self.style.WARNING(
                    "Rate limit hit for %s, will retry in next run" % to_email
                ))
            else:
                self.stdout.write(self.style.ERROR("SMTP Error: %s" % str(e)))
            return False
            
        except Exception as e:
            self.stdout.write(self.style.ERROR("Error sending email to %s: %s" % (to_email, str(e))))
            return False

    def process_monthly_data(self, entries_by_week, all_active_users=None, project_ids=None):
        """Process entries into project-centric format with weeks"""
        project_data = {}
        column_totals = {}  # Track totals for each week
        
        # Get all week numbers from entries_by_week
        week_numbers = sorted([int(k) for k in entries_by_week.keys()]) if entries_by_week else []
        
        # Initialize all projects and their active users with zero hours
        # This ensures users who worked on these projects before but have no entries
        # in the current period still appear in the report
        if all_active_users is not None and project_ids is not None:
            # Get project information
            projects = Project.objects.filter(identifier__in=project_ids)
            for project in projects:
                project_code = project.identifier
                # Get users who have worked on this specific project
                project_user_ids = TimeEntry.objects.filter(
                    project__identifier=project_code
                ).values_list('user', flat=True).distinct()
                project_active_users = all_active_users.filter(id__in=project_user_ids)
                
                # Initialize project structure
                if project_code not in project_data:
                    project_data[project_code] = {
                        'total_hours': 0,
                        'users': {},
                        'column_totals': {week: 0 for week in week_numbers}
                    }
                
                # Initialize all active users for this project with zero hours
                for user in project_active_users:
                    username = '%s %s' % (user.firstname, user.lastname)
                    username = username.strip()
                    if username not in project_data[project_code]['users']:
                        project_data[project_code]['users'][username] = {
                            'hours': 0,
                            'activities': {}
                        }
        
        # Process each week's entries
        for week_num, entries in entries_by_week.items():
            column_totals[week_num] = 0  # Initialize week total
            for entry in entries:
                project_code = entry.project.identifier if entry.project else 'No Project'
                username = '%s %s' % (entry.user.firstname, entry.user.lastname)
                username = username.strip()
                activity = entry.comments if entry.comments else (entry.activity.name if entry.activity else 'No Activity')
                hours = float(entry.hours)
                
                # Add to column total for this week
                column_totals[week_num] += hours
                
                # Initialize project if needed
                if project_code not in project_data:
                    project_data[project_code] = {
                        'total_hours': 0,
                        'users': {},
                        'column_totals': {week: 0 for week in week_numbers}
                    }
                
                # Add to project total
                project_data[project_code]['total_hours'] += hours
                
                # Initialize user if not exists
                if username not in project_data[project_code]['users']:
                    project_data[project_code]['users'][username] = {
                        'hours': 0,
                        'activities': {}
                    }
                
                # Add to user total
                project_data[project_code]['users'][username]['hours'] += hours
                
                # Initialize activity if needed
                if activity not in project_data[project_code]['users'][username]['activities']:
                    project_data[project_code]['users'][username]['activities'][activity] = {}
                
                # Add hours to activity week
                project_data[project_code]['users'][username]['activities'][activity][week_num] = hours
        
        # Add column totals to each project
        for project in project_data.values():
            project['column_totals'] = column_totals
        
        return dict(sorted(project_data.items()))

    def get_db_credentials(self):
        """Get database credentials"""
        credentials = {
            'POSTGRES_DB': os.environ.get('POSTGRES_DB'),
            'POSTGRES_USER': os.environ.get('POSTGRES_USER'),
            'POSTGRES_PASSWORD': os.environ.get('POSTGRES_PASSWORD')
        }
        return credentials

    def process_entries(self, entries, all_active_users=None, project_ids=None):
        """Process entries for weekly report format"""
        report_data = {}
        total_hours = 0  # Track total hours
        
        # Initialize all projects and their active users with zero hours
        # This ensures users who worked on these projects before but have no entries
        # in the current period still appear in the report
        if all_active_users is not None and project_ids is not None:
            # Get project information
            projects = Project.objects.filter(identifier__in=project_ids)
            for project in projects:
                project_code = project.identifier
                project_name = project.name
                project_key = "%s (%s)" % (project_name, project_code)
                
                # Get users who have worked on this specific project
                project_user_ids = TimeEntry.objects.filter(
                    project__identifier=project_code
                ).values_list('user', flat=True).distinct()
                project_active_users = all_active_users.filter(id__in=project_user_ids)
                
                # Initialize project structure
                if project_key not in report_data:
                    report_data[project_key] = {
                        'total_hours': 0,
                        'users': {},
                        'total_column': 0
                    }
                
                # Initialize all active users for this project with zero hours
                for user in project_active_users:
                    username = '%s %s' % (user.firstname, user.lastname)
                    username = username.strip()
                    if username not in report_data[project_key]['users']:
                        report_data[project_key]['users'][username] = {
                            'hours': 0,
                            'activities': {}
                        }
        
        for entry in entries:
            project_code = entry.project.identifier if entry.project else 'No Project'
            project_name = entry.project.name if entry.project else 'No Project'
            project_code = "%s (%s)" % (project_name, project_code)  # Update project_code to include name
            username = '%s %s' % (entry.user.firstname, entry.user.lastname)
            username = username.strip()
            hours = float(entry.hours)
            total_hours += hours  # Add to total
            
            # Use comments as activities if they exist
            activity = entry.comments if entry.comments else (entry.activity.name if entry.activity else 'No Activity')
            
            # Initialize project if not exists
            if project_code not in report_data:
                report_data[project_code] = {
                    'total_hours': 0,
                    'users': {},
                    'total_column': 0  # Add total column for weekly
                }
            
            # Add to project total
            report_data[project_code]['total_hours'] += hours
            report_data[project_code]['total_column'] += hours  # Add to total column
            
            # Initialize user if not exists
            if username not in report_data[project_code]['users']:
                report_data[project_code]['users'][username] = {
                    'hours': 0,
                    'activities': {}
                }
            
            # Add to user total
            report_data[project_code]['users'][username]['hours'] += hours
            
            # Add to activity data
            if activity not in report_data[project_code]['users'][username]['activities']:
                report_data[project_code]['users'][username]['activities'][activity] = {
                    'hours': hours
                }
            else:
                report_data[project_code]['users'][username]['activities'][activity]['hours'] += hours

        return dict(sorted(report_data.items()))

    def handle(self, *args, **options):
        print "\n=== Starting PI Report Generation (with zero hours) ==="
        
        start_date, end_date = self.get_report_dates(options.get('monthly', False), options)
        print "\nDate Range: %s to %s" % (start_date, end_date)
        
        try:
            # Get credentials from file
            db_creds = self.get_db_credentials()
            
            connection = psycopg2.connect(
                host='database1',
                database=db_creds.get('POSTGRES_DB'),
                user=db_creds.get('POSTGRES_USER'),
                password=db_creds.get('POSTGRES_PASSWORD')
            )
            cursor = connection.cursor()
            
            try:
                # Get all projects and their Financial PI emails
                cursor.execute("""
                    SELECT DISTINCT cv.value as pi_email, 
                           array_agg(p.identifier) as project_ids
                    FROM projects p
                    JOIN custom_values cv ON cv.customized_id = p.id
                    JOIN custom_fields cf ON cf.id = cv.custom_field_id
                    WHERE cf.name = 'Financial PI'
                    AND p.status = 1
                    AND cv.value IS NOT NULL 
                    AND cv.value != ''
                    GROUP BY cv.value;
                """)
                pi_mappings = cursor.fetchall()
            finally:
                cursor.close()
                connection.close()
            
            for pi_email, project_ids in pi_mappings:
                # Handle test email case first
                if options.get('test_email'):
                    to_emails = [options.get('test_email')]
                else:
                    # If there's a comma, handle multiple emails, otherwise treat as single email
                    if ',' in pi_email:
                        email_addresses = [email.strip() for email in pi_email.split(',')]
                        # Get all valid emails
                        valid_emails = [email for email in email_addresses if self.is_email(email)]
                        if not valid_emails:
                            self.stdout.write(self.style.WARNING(
                                'Skipping invalid email(s): %s' % pi_email
                            ))
                            continue
                        to_emails = valid_emails
                    else:
                        # Single email case
                        if not self.is_email(pi_email.strip()):
                            self.stdout.write(self.style.WARNING(
                                'Skipping invalid email: %s' % pi_email
                            ))
                            continue
                        to_emails = [pi_email.strip()]

                self.stdout.write('\nProcessing Financial PI: %s' % ', '.join(to_emails))
                self.stdout.write('Projects: %s' % ', '.join(project_ids))

                # Get all active users who have EVER worked on these projects
                # This ensures users who worked on projects before but have no entries
                # in the current period still appear in the report
                all_user_ids = TimeEntry.objects.filter(
                    project__identifier__in=project_ids
                ).values_list('user', flat=True).distinct()
                
                if not all_user_ids:
                    self.stdout.write(self.style.WARNING(
                        '  No users found for projects: %s - skipping' % ', '.join(project_ids)
                    ))
                    continue
                
                all_active_users = RedmineUser.objects.filter(
                    id__in=all_user_ids,
                    status=1  # Only active users
                )
                
                if not all_active_users.exists():
                    self.stdout.write(self.style.WARNING(
                        '  No active users found for projects: %s - skipping' % ', '.join(project_ids)
                    ))
                    continue

                if options.get('monthly'):
                    # Get entries for each week
                    entries_by_week = {}
                    current_date = start_date
                    week_num = 1
                    week_numbers = []
                    
                    while current_date <= end_date:
                        week_end = min(current_date + timedelta(days=6), end_date)
                        
                        entries = TimeEntry.objects.filter(
                            project__identifier__in=project_ids,
                            spent_on__range=[current_date, week_end]
                        ).select_related('user', 'project', 'activity')
                        
                        if entries.exists():
                            entries_by_week[str(week_num)] = entries
                            week_numbers.append(str(week_num))
                        
                        current_date += timedelta(days=7)
                        week_num += 1
                    
                    # Process data into monthly format
                    monthly_data = self.process_monthly_data(entries_by_week, all_active_users, project_ids)
                    
                    context = {
                        'weekly_data': monthly_data,
                        'start_date': start_date,
                        'end_date': end_date,
                        'monthly': True,
                        'week_numbers': week_numbers
                    }
                else:
                    # Weekly report
                    entries = TimeEntry.objects.filter(
                        project__identifier__in=project_ids,
                        spent_on__range=[start_date, end_date]
                    ).select_related('user', 'project', 'activity')

                    context = {
                        'entries': self.process_entries(entries, all_active_users, project_ids),
                        'start_date': start_date,
                        'end_date': end_date,
                        'monthly': False
                    }

                # Always generate report, even if no entries (to show users with zero hours)
                html_content = render_to_string('emails/pi_monthly_report.html', context)
                subject = 'ND P&P PI %s Report (%s - %s) [Includes Zero Hours]' % (
                    'Monthly' if options.get('monthly') else 'Weekly',
                    start_date.strftime('%b %d'),
                    end_date.strftime('%b %d')
                )

                # Check if --print flag is set
                if options.get('print'):
                    self.stdout.write("\n" + "="*80)
                    self.stdout.write("REPORT FOR: %s" % ', '.join(to_emails))
                    self.stdout.write("SUBJECT: %s" % subject)
                    self.stdout.write("="*80)
                    self.stdout.write(html_content)
                    self.stdout.write("="*80 + "\n")
                else:
                    # Send to each valid email
                    for to_email in to_emails:
                        if self.send_notification(to_email, html_content, subject):
                            self.stdout.write(self.style.SUCCESS('Sent report to %s' % to_email))
                        else:
                            self.stdout.write(self.style.ERROR('Failed to send report to %s' % to_email))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR('Error: %s' % str(e)))
            raise
        
        print "\n=== PI Report Generation Complete ===\n"

