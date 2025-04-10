from django.core.management.base import BaseCommand
from django.template.loader import get_template, render_to_string
from django.utils import timezone
from django.db import connection
from django.core.mail import send_mail
from datetime import datetime, timedelta, date
from time_management.models import RedmineUser, TimeEntry, Project, Team, TeamMember, Enumeration
from django.contrib.auth.models import User
import logging
import html2text
import smtplib
from email.mime.text import MIMEText
import psycopg2
import time
from email.mime.multipart import MIMEMultipart
from time import sleep

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
        
        if monthly:
            # Get last day of previous month
            if today.month == 1:  # January
                prev_month_end = today.replace(year=today.year-1, month=12, day=31)
            else:
                prev_month_end = today.replace(day=1) - timedelta(days=1)
            
            # Find the last Friday of previous month
            last_friday = prev_month_end
            while last_friday.weekday() != 4:  # 4 is Friday
                last_friday -= timedelta(days=1)
            
            # Start date is the day after the last Friday of previous month
            start_date = last_friday + timedelta(days=1)
            # End date is today
            end_date = today
            
            return start_date, end_date
        else:
            # Weekly report logic remains unchanged
            end_date = today - timedelta(days=(today.weekday() + 3) % 7)
            start_date = end_date - timedelta(days=6)
            return start_date, end_date

    def send_notification(self, to_email, message_body, message_subject):
        msg = MIMEText(message_body, 'html')
        msg['Subject'] = message_subject
        msg['From'] = 'noreply@turbo.crc.nd.edu'
        msg['To'] = to_email
        
        smtp = smtplib.SMTP('dockerhost')
        smtp.sendmail('noreply@turbo.crc.nd.edu', [to_email], msg.as_string())
        smtp.close()
        
        time.sleep(60)  # Wait 5 seconds between emails

    def send_supervisor_report(self, supervisor_email, start_date, end_date, options, team_members):
        print("\nProcessing supervisor:", supervisor_email)
        
        # If test_email is set, use that instead of actual supervisor email
        to_email = options.get('test_email', supervisor_email)
        
        # For monthly reports, break into weeks
        weekly_data = {}
        current_date = start_date
        
        # Calculate all week start dates for the month
        week_starts = []
        while current_date <= end_date:
            week_starts.append(current_date)
            current_date += timedelta(days=7)
        
        # Process each week
        for week_start in week_starts:
            week_end = min(week_start + timedelta(days=6), end_date)
            week_label = "Week of {}".format(week_start.strftime("%b %d"))
            
            # Get entries for this week
            entries = TimeEntry.objects.filter(
                user__in=team_members,
                spent_on__range=[week_start, week_end]
            ).select_related('user', 'project', 'activity')
            
            if entries.exists():
                weekly_data[week_label] = self.process_entries(entries)
                self.stdout.write(
                    '\nProcessing week {} to {}: {} entries'.format(
                        week_start.strftime('%Y-%m-%d'),
                        week_end.strftime('%Y-%m-%d'),
                        entries.count()
                    )
                )

        context = {
            'weekly_data': weekly_data,
            'start_date': start_date,
            'end_date': end_date,
            'monthly': True
        }
        
        print("Generating email content...")
        # Generate the report content
        template = get_template('emails/supervisor_monthly_report.html')
        message = template.render(context)
        
        # Set subject based on report type
        subject = 'Turbomachinery Lab Monthly Hours Report' if options.get('monthly') else 'Turbomachinery Lab Weekly Hours Report'
        
        print("Sending email...")
        # Send the email and check result
        if self.send_notification(to_email, message, subject):
            print("Sent report to", to_email)
        else:
            print("Failed to send report to", to_email)
            # Sleep here to give SMTP server time to recover
            time.sleep(500)

    def process_entries(self, entries):
        report_data = {}
        
        for entry in entries:
            username = '%s %s' % (entry.user.firstname, entry.user.lastname)
            username = username.strip()
            project_code = entry.project.identifier if entry.project else 'No Project'
            hours = float(entry.hours)
            
            # Use comments as activities if they exist
            activity = entry.comments if entry.comments else (entry.activity.name if entry.activity else 'No Activity')
            
            # Initialize user if not exists
            if username not in report_data:
                report_data[username] = {
                    'total_hours': 0,
                    'projects': {}
                }
            
            # Add to user total
            report_data[username]['total_hours'] += hours
            
            # Initialize project if not exists
            if project_code not in report_data[username]['projects']:
                report_data[username]['projects'][project_code] = {
                    'total_hours': 0,
                    'activities': {}
                }
            
            # Add to project total
            report_data[username]['projects'][project_code]['total_hours'] += hours
            
            # Add to activity data
            if activity not in report_data[username]['projects'][project_code]['activities']:
                report_data[username]['projects'][project_code]['activities'][activity] = hours
            else:
                report_data[username]['projects'][project_code]['activities'][activity] += hours

        return dict(sorted(report_data.items()))

    def get_report_data(self, start_date, end_date, monthly=False):
        if not monthly:
            # Weekly report - use existing person grouping
            return self.get_person_grouped_data(start_date, end_date)
        else:
            # Monthly report - group by week first
            weeks_data = {}
            current_date = start_date
            
            while current_date <= end_date:
                week_end = min(current_date + timedelta(days=6), end_date)
                week_label = "Week of {0}".format(current_date.strftime("%b %d"))
                
                # Get data for this week
                week_data = self.get_person_grouped_data(current_date, week_end)
                if week_data:  # Only add weeks with data
                    weeks_data[week_label] = week_data
                current_date += timedelta(days=7)
            
            return weeks_data

    def get_person_grouped_data(self, start_date, end_date):
        person_entries = {}
        
        # First get all unique users for this period
        users = TimeEntry.objects.filter(
            date__range=[start_date, end_date]
        ).values_list('user', 'user__first_name', 'user__last_name').distinct()
        
        # Then process each user's entries
        for user_id, first_name, last_name in users:
            full_name = "{0} {1}".format(first_name, last_name).strip()
            
            # Get ALL entries for this user in the date range
            user_entries = TimeEntry.objects.filter(
                user_id=user_id,
                date__range=[start_date, end_date]
            ).select_related('project').order_by('date', 'project__code')
            
            if not user_entries:
                continue
            
            # Initialize user data
            person_entries[full_name] = {
                'total_hours': 0,
                'projects': {}
            }
            
            # Group all entries by project
            for entry in user_entries:
                project_code = entry.project.code if entry.project else 'No Project'
                activity = entry.activity or 'No Activity'
                hours = float(entry.hours)
                
                # Add to user total
                person_entries[full_name]['total_hours'] += hours
                
                # Ensure project exists
                if project_code not in person_entries[full_name]['projects']:
                    person_entries[full_name]['projects'][project_code] = {
                        'total_hours': 0,
                        'activities': {}
                    }
                
                # Add to project total
                person_entries[full_name]['projects'][project_code]['total_hours'] += hours
                
                # Add or update activity hours
                if activity not in person_entries[full_name]['projects'][project_code]['activities']:
                    person_entries[full_name]['projects'][project_code]['activities'][activity] = 0
                person_entries[full_name]['projects'][project_code]['activities'][activity] += hours
        
        # Sort by total hours descending, then by name
        return dict(sorted(
            person_entries.items(),
            key=lambda x: (-x[1]['total_hours'], x[0].lower())
        ))

    def process_monthly_data(self, entries_by_week):
        """Process entries into project-centric format with weeks"""
        monthly_data = {}
        
        # Process each week's entries
        for week_num, entries in entries_by_week.items():
            for entry in entries:
                employee = "{0} {1}".format(entry.user.firstname, entry.user.lastname).strip()
                project = entry.project.identifier if entry.project else 'No Project'
                activity = entry.comments if entry.comments else (entry.activity.name if entry.activity else 'No Activity')
                hours = float(entry.hours)
                
                # Initialize employee if needed
                if employee not in monthly_data:
                    monthly_data[employee] = {
                        'projects': {},
                        'column_totals': {week: 0 for week in week_numbers}  # Initialize week totals
                    }
                
                # Initialize project if needed
                if project not in monthly_data[employee]['projects']:
                    monthly_data[employee]['projects'][project] = {
                        'weeks': {week: 0 for week in week_numbers},  # Initialize all weeks
                        'entries': {},
                        'total_hours': 0
                    }
                
                # Add hours to project week
                monthly_data[employee]['projects'][project]['weeks'][week_num] = monthly_data[employee]['projects'][project]['weeks'].get(week_num, 0) + hours
                monthly_data[employee]['projects'][project]['total_hours'] += hours
                
                # Add to column totals
                monthly_data[employee]['column_totals'][week_num] = monthly_data[employee]['column_totals'].get(week_num, 0) + hours
                
                # Initialize activity if needed
                if activity not in monthly_data[employee]['projects'][project]['entries']:
                    monthly_data[employee]['projects'][project]['entries'][activity] = {week: 0 for week in week_numbers}
                
                # Add hours to activity week
                monthly_data[employee]['projects'][project]['entries'][activity][week_num] = hours
        
        return monthly_data

    def get_project_and_subprojects(self, project_ids):
        """Get all projects and their subprojects"""
        with connection.cursor() as cursor:
            cursor.execute("""
                WITH RECURSIVE subprojects AS (
                    -- Base case: get the initial projects
                    SELECT id, identifier, parent_id
                    FROM projects 
                    WHERE identifier = ANY(%s)
                    
                    UNION ALL
                    
                    -- Recursive case: get child projects
                    SELECT p.id, p.identifier, p.parent_id
                    FROM projects p
                    INNER JOIN subprojects sp ON p.parent_id = sp.id
                    WHERE p.status = 1
                )
                SELECT identifier FROM subprojects;
            """, [project_ids])
            
            return [row[0] for row in cursor.fetchall()]

    def get_db_credentials(self):
        """Get database credentials"""
        credentials = {
            'POSTGRES_DB': 'redmine',
            'POSTGRES_USER': 'postgres',
            'POSTGRES_PASSWORD': "Let's go turbo!"
        }
        return credentials

    def handle(self, *args, **options):
        print "\n=== Starting Supervisor Report Generation ==="
        
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
            
            cursor.execute("""
                SELECT DISTINCT cv.value 
                FROM custom_values cv 
                JOIN custom_fields cf ON cf.id = cv.custom_field_id 
                WHERE cf.name = 'Supervisor Notification Emails'
                AND cv.value IS NOT NULL 
                AND cv.value != ''
                ORDER BY cv.value;
            """)
            supervisors = [row[0] for row in cursor.fetchall()]

            self.stdout.write('\nFound {} supervisors\n'.format(len(supervisors)))

            for supervisor_email in supervisors:
                self.stdout.write('\nProcessing supervisor: {}'.format(supervisor_email))

                # Get team members for this supervisor only
                cursor.execute("""
                    SELECT u.id 
                    FROM users u
                    JOIN custom_values cv ON cv.customized_id = u.id
                    JOIN custom_fields cf ON cf.id = cv.custom_field_id
                    WHERE cf.name = 'Supervisor Notification Emails'
                    AND cv.value = %s
                    AND u.status = 1;
                """, [supervisor_email])
                team_members = [row[0] for row in cursor.fetchall()]
                team_members = RedmineUser.objects.filter(id__in=team_members)

                if team_members:
                    if options.get('monthly', False):
                        entries_by_week = {}
                        current_date = start_date
                        week_num = 1
                        week_numbers = []
                        
                        while current_date <= end_date:
                            week_end = min(current_date + timedelta(days=6), end_date)
                            
                            # Get all project IDs including subprojects
                            project_entries = TimeEntry.objects.filter(
                                user__in=team_members,
                                spent_on__range=[current_date, week_end]
                            ).values_list('project__identifier', flat=True).distinct()
                            
                            all_project_ids = self.get_project_and_subprojects(list(project_entries))
                            
                            # Get entries for main projects and subprojects
                            entries = TimeEntry.objects.filter(
                                user__in=team_members,
                                project__identifier__in=all_project_ids,
                                spent_on__range=[current_date, week_end]
                            ).select_related('user', 'project', 'activity')
                            
                            if entries.exists():
                                entries_by_week[str(week_num)] = entries
                                week_numbers.append(str(week_num))
                            
                            current_date += timedelta(days=7)
                            week_num += 1
                        
                        # Process data into monthly format
                        monthly_data = self.process_monthly_data(entries_by_week)
                        
                        context = {
                            'weekly_data': monthly_data,
                            'start_date': start_date,
                            'end_date': end_date,
                            'monthly': True,
                            'week_numbers': week_numbers  # Add week numbers to context
                        }
                    else:
                        # Weekly report for this supervisor
                        entries = TimeEntry.objects.filter(
                            user__in=team_members,
                            spent_on__range=[start_date, end_date]
                        ).select_related('user', 'project', 'activity')

                        context = {
                            'entries': self.process_entries(entries),
                            'start_date': start_date,
                            'end_date': end_date,
                            'monthly': False
                        }

                    if entries.exists():
                        html_content = render_to_string('emails/supervisor_monthly_report.html', context)
                        subject = 'NDTL Supervisor %s Report (%s - %s)' % (
                            'Monthly' if options.get('monthly', False) else 'Weekly',
                            start_date.strftime('%b %d'),
                            end_date.strftime('%b %d')
                        )

                        # Send to test email but keep supervisor name in subject
                        to_email = options.get('test_email') if options.get('test_email') else supervisor_email
                        if options.get('test_email'):
                            subject = '[%s] %s' % (supervisor_email, subject)

                        self.send_notification(to_email, html_content, subject)
                        self.stdout.write(self.style.SUCCESS('Sent report to %s' % to_email))

        except Exception as e:
            self.stdout.write(self.style.ERROR('Error: {}'.format(str(e))))
            raise 