from django.core.management.base import BaseCommand
from django.template.loader import get_template
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
            print("Processing monthly report...")
            current = start_date
            while current < end_date:  # Changed <= to <
                print("Processing week starting %s" % current)
                # Find Saturday (start of week)
                week_start = current
                
                # Find Friday (end of week)
                week_end = week_start + timedelta(days=6)
                if week_end > end_date:
                    week_end = end_date
                
                print("Fetching entries for %s to %s" % (week_start, week_end))
                # Get entries for this week
                entries = TimeEntry.objects.filter(
                    spent_on__range=[week_start, week_end],
                    user_id__in=team_members
                ).select_related('user', 'project', 'activity')
                
                print("Processing %d entries" % entries.count())
                # Process entries into report data
                report_data = self.process_entries(entries)
                
                weekly_ranges.append({
                    'start': week_start,
                    'end': week_end,
                    'entries': report_data
                })
                
                current = week_end + timedelta(days=1)
                print("Week processed")
                
                if current >= end_date:  # Added explicit break condition
                    break
        else:
            print("Processing weekly report...")
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
        
        print("Generating email content...")
        # Generate the report content
        template = get_template('emails/supervisor_monthly_report.html')
        message = template.render({
            'supervisor_name': supervisor_email,
            'start_date': start_date,
            'end_date': end_date,
            'weekly_ranges': weekly_ranges
        })
        
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
            project_code = entry.project.identifier
            if project_code not in report_data:
                report_data[project_code] = {
                    'total_hours': 0.0,
                    'users': {}
                }
            
            username = '%s %s' % (entry.user.firstname, entry.user.lastname)
            if username not in report_data[project_code]['users']:
                report_data[project_code]['users'][username] = {
                    'total_hours': 0.0,
                    'activities': {}
                }
            
            activity = entry.comments or (entry.activity.name if entry.activity else '')
            if activity:
                activity_key = activity.strip()
                if activity_key not in report_data[project_code]['users'][username]['activities']:
                    report_data[project_code]['users'][username]['activities'][activity_key] = 0.0  # Just store hours
                
                # Add hours
                hours = float(entry.hours)
                report_data[project_code]['users'][username]['activities'][activity_key] += hours
                report_data[project_code]['users'][username]['total_hours'] += hours
                report_data[project_code]['total_hours'] += hours
        
        return report_data

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

    def handle(self, *args, **options):
        start_date = options.get('start_date')
        end_date = options.get('end_date')
        monthly = options.get('monthly', False)
        test_email = options.get('test_email')

        try:
            # Get supervisors using direct PostgreSQL query
            connection = psycopg2.connect(
                host='database1',
                database='redmine',
                user='postgres',
                password="Let's go turbo!"
            )
            cursor = connection.cursor()
            
            if test_email:
                # If test email provided, use it as the only supervisor
                supervisors = [(test_email,)]
            else:
                # Get all supervisors from Redmine database
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
            
            self.stdout.write('\nFound {} supervisors\n'.format(len(supervisors)))
            
            for supervisor in supervisors:
                supervisor_email = supervisor[0]
                self.stdout.write('\nProcessing supervisor: {}'.format(supervisor_email))
                
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
                
                # Generate report content first
                self.stdout.write('Processing {} report...'.format('monthly' if monthly else 'weekly'))
                self.stdout.write('Generating email content...')
                
                subject, text_content, html_content = self.generate_report_content(
                    supervisor_email, start_date, end_date, monthly
                )
                
                # Then try to send email with retries
                max_retries = 3
                retry_delay = 5  # 5 seconds between retries
                
                for attempt in range(max_retries):
                    try:
                        send_mail(
                            subject=subject,
                            message=text_content,
                            from_email=None,  # Uses DEFAULT_FROM_EMAIL
                            recipient_list=[supervisor_email],
                            html_message=html_content,
                            fail_silently=False,
                        )
                        self.stdout.write(self.style.SUCCESS(
                            'Successfully sent report to {}'.format(supervisor_email)
                        ))
                        break  # Exit retry loop on success
                        
                    except Exception as e:
                        if attempt < max_retries - 1:
                            self.stdout.write(self.style.WARNING(
                                'Email attempt {} failed for {}, retrying in {} seconds... Error: {}'.format(
                                    attempt + 1, supervisor_email, retry_delay, str(e)
                                )
                            ))
                            sleep(retry_delay)
                        else:
                            self.stdout.write(self.style.ERROR(
                                'Failed to send email to {} after {} attempts. Error: {}'.format(
                                    supervisor_email, max_retries, str(e)
                                )
                            ))
                            
        except Exception as e:
            self.stdout.write(self.style.ERROR('Error: {}'.format(str(e))))
            raise

    def generate_report_content(self, supervisor, start_date, end_date, monthly):
        # Existing report generation code...
        pass 