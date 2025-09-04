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

from time_management.models import Team

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
        parser.add_argument(
            '--manager_email',
            type=str,
            help='Send report only to this specific manager (use their login username, e.g., jsmith)',
        )

    def get_report_dates(self, monthly=False, options=None):
        """Get start and end dates for the report period."""
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
        msg = MIMEText(message_body, 'html')
        msg['Subject'] = message_subject
        msg['From'] = 'noreply@turbo.crc.nd.edu'
        msg['To'] = to_email
        
        smtp = smtplib.SMTP('dockerhost')
        smtp.sendmail('noreply@turbo.crc.nd.edu', [to_email], msg.as_string())
        smtp.close()
        
        time.sleep(60)  # Wait between emails

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
        grand_total = 0
        project_totals = {}  # Track project totals
        
        for entry in entries:
            username = '%s %s' % (entry.user.firstname, entry.user.lastname)
            username = username.strip()
            project_code = entry.project.identifier if entry.project else 'No Project'
            project_name = entry.project.name if entry.project else 'No Project'
            project_code = "%s (%s)" % (project_name, project_code)  # Update project_code to include name
            hours = float(entry.hours)
            grand_total += hours
            
            # Track project totals
            if project_code not in project_totals:
                project_totals[project_code] = {
                    'total_hours': 0,
                    'activities': {}
                }
            project_totals[project_code]['total_hours'] += hours
            
            activity = entry.comments if entry.comments else (entry.activity.name if entry.activity else 'No Activity')
            if activity not in project_totals[project_code]['activities']:
                project_totals[project_code]['activities'][activity] = 0
            project_totals[project_code]['activities'][activity] += hours
            
            # Process individual entries - consolidate by username
            if username not in report_data:
                report_data[username] = {
                    'total_hours': 0,
                    'projects': {}
                }
            report_data[username]['total_hours'] += hours
            
            if project_code not in report_data[username]['projects']:
                report_data[username]['projects'][project_code] = {
                    'total_hours': 0,
                    'activities': {}
                }
            report_data[username]['projects'][project_code]['total_hours'] += hours
            
            if activity not in report_data[username]['projects'][project_code]['activities']:
                report_data[username]['projects'][project_code]['activities'][activity] = hours
            else:
                report_data[username]['projects'][project_code]['activities'][activity] += hours

        # Add project totals at the end
        report_data['PROJECT TOTALS'] = {
            'total_hours': grand_total,
            'projects': project_totals
        }

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
            'POSTGRES_DB': os.environ.get('POSTGRES_DB'),
            'POSTGRES_USER': os.environ.get('POSTGRES_USER'),
            'POSTGRES_PASSWORD': os.environ.get('POSTGRES_PASSWORD')
        }
        return credentials

    def get_supervisor_name(self, supervisor_email):
        """Get supervisor's name from their email"""
        try:
            cursor = connection.cursor()
            # Extract username part before @ from email
            username = supervisor_email.split('@')[0]
            cursor.execute("""
                SELECT firstname, lastname 
                FROM users 
                WHERE login = %s
                AND status = 1;
            """, [username])
            
            result = cursor.fetchone()
            if result:
                firstname, lastname = result
                return "%s %s" % (firstname, lastname)
            return supervisor_email  # Fallback to email if name not found
            
        except Exception as e:
            print "Error getting supervisor name: %s" % str(e)  # Using Python 2 print
            return supervisor_email  # Fallback to email on error

    def process_monthly_entries(self, entries, start_date, end_date):
        """Process entries for monthly report with weekly columns"""
        report_data = {}
        
        # Calculate week ranges
        current_date = start_date
        week_ranges = []
        week_num = 1
        while current_date <= end_date:
            week_end = min(current_date + timedelta(days=6), end_date)
            week_ranges.append((week_num, current_date, week_end))
            current_date = week_end + timedelta(days=1)
            week_num += 1
        
        # Process entries by user and week
        for entry in entries:
            username = '%s %s' % (entry.user.firstname, entry.user.lastname)
            username = username.strip()
            project_code = entry.project.identifier if entry.project else 'No Project'
            hours = float(entry.hours)
            activity = entry.comments if entry.comments else (entry.activity.name if entry.activity else 'No Activity')
            
            # Find which week this entry belongs to
            entry_week = None
            for week_num, week_start, week_end in week_ranges:
                if week_start <= entry.spent_on <= week_end:
                    entry_week = week_num
                    break
            
            if entry_week is None:
                continue
            
            # Initialize user data structure
            if username not in report_data:
                report_data[username] = {
                    'projects': {},
                    'total_hours': 0,
                    'weekly_totals': {w[0]: 0 for w in week_ranges}  # Add weekly totals tracking
                }
            
            # Initialize project
            if project_code not in report_data[username]['projects']:
                report_data[username]['projects'][project_code] = {
                    'weeks': {w[0]: 0 for w in week_ranges},
                    'activities': {},
                    'total_hours': 0
                }
            
            # Initialize activity
            if activity not in report_data[username]['projects'][project_code]['activities']:
                report_data[username]['projects'][project_code]['activities'][activity] = {
                    'weeks': {w[0]: 0 for w in week_ranges}
                }
            
            # Add hours to appropriate week
            report_data[username]['projects'][project_code]['weeks'][entry_week] = \
                report_data[username]['projects'][project_code]['weeks'].get(entry_week, 0) + hours
            report_data[username]['projects'][project_code]['activities'][activity]['weeks'][entry_week] = \
                report_data[username]['projects'][project_code]['activities'][activity]['weeks'].get(entry_week, 0) + hours
            report_data[username]['projects'][project_code]['total_hours'] += hours
            report_data[username]['total_hours'] += hours
            report_data[username]['weekly_totals'][entry_week] += hours  # Add to weekly total
        
        return report_data, [w[0] for w in week_ranges]

    def handle(self, *args, **options):
        print "\n=== Starting Team Manager Report Generation ==="
        
        start_date, end_date = self.get_report_dates(options.get('monthly', False), options)
        print "\nDate Range: %s to %s" % (start_date, end_date)
        
        try:
            managers = Team.objects.select_related('manager').all()
            
            # Filter by specific manager if requested
            if options.get('manager_email'):
                managers = managers.filter(manager__login=options['manager_email'])
                if not managers.exists():
                    print "No team found for manager with login: %s" % options['manager_email']
                    return
            
            for team in managers:
                manager = team.manager
                print '\nProcessing manager: {} {}'.format(manager.firstname, manager.lastname)
                
                # Get team members
                team_members = TeamMember.objects.filter(team=team).values_list('member', flat=True)
                
                # Get time entries for all team members
                entries = TimeEntry.objects.filter(
                    user__in=team_members,
                    spent_on__range=[start_date, end_date]
                ).select_related('user', 'project', 'activity')

                if entries.exists():
                    if options.get('monthly', False):
                        processed_data, week_numbers = self.process_monthly_entries(entries, start_date, end_date)
                        context = {
                            'entries': processed_data,
                            'week_numbers': week_numbers,
                            'start_date': start_date,
                            'end_date': end_date,
                            'monthly': True,
                            'supervisor_name': "%s %s" % (manager.firstname, manager.lastname)
                        }
                    else:
                        processed_entries = self.process_entries(entries)
                        context = {
                            'entries': processed_entries,
                            'start_date': start_date,
                            'end_date': end_date,
                            'monthly': False,
                            'supervisor_name': "%s %s" % (manager.firstname, manager.lastname)
                        }

                    html_content = render_to_string('emails/supervisor_monthly_report.html', context)
                    subject = 'ND P&P Team Manager %s Report (%s - %s)' % (
                        'Monthly' if options.get('monthly', False) else 'Weekly',
                        start_date.strftime('%b %d'),
                        end_date.strftime('%b %d')
                    )

                    # Get manager's email
                    cursor = connection.cursor()
                    cursor.execute("""
                        SELECT address 
                        FROM email_addresses 
                        WHERE user_id = %s 
                        AND is_default = true
                        LIMIT 1;
                    """, [manager.id])
                    result = cursor.fetchone()
                    manager_email = result[0] if result else None
                    
                    if manager_email:
                        to_email = options.get('test_email') if options.get('test_email') else manager_email
                        self.send_notification(to_email, html_content, subject)
                        print "Sent report to %s" % to_email

        except Exception as e:
            print "Error: %s" % str(e)
            raise 