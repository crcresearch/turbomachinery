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
            hours = float(entry.hours)
            grand_total += hours
            
            # Track project totals
            if project_code not in project_totals:
                project_totals[project_code] = {
                    'total_hours': 0,
                    'activities': {}
                }
            project_totals[project_code]['total_hours'] += hours
            
            # Track activity within project totals
            activity = entry.comments if entry.comments else (entry.activity.name if entry.activity else 'No Activity')
            if activity not in project_totals[project_code]['activities']:
                project_totals[project_code]['activities'][activity] = 0
            project_totals[project_code]['activities'][activity] += hours
            
            # Rest of the existing user/project processing...
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

        # Add project totals section before the grand total
        sorted_projects = sorted(project_totals.items(), key=lambda x: (-x[1]['total_hours'], x[0]))
        report_data['PROJECT TOTALS'] = {
            'total_hours': grand_total,
            'projects': dict(sorted_projects)
        }

        # Add grand total at the end
        report_data['TOTAL'] = {
            'total_hours': grand_total,
            'projects': {}
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
            'POSTGRES_DB': 'redmine',
            'POSTGRES_USER': 'postgres',
            'POSTGRES_PASSWORD': "Let's go turbo!"
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

    def handle(self, *args, **options):
        print "\n=== Starting Team Manager Report Generation ==="
        
        start_date, end_date = self.get_report_dates(options.get('monthly', False), options)
        print "\nDate Range: %s to %s" % (start_date, end_date)
        
        try:
            managers = Team.objects.select_related('manager').all()
            
            for team in managers:
                manager = team.manager
                print '\nProcessing manager: {} {}'.format(manager.firstname, manager.lastname)
                
                # Get manager's email from Redmine database
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
                
                if not manager_email:
                    print "Warning: No email found for manager %s %s" % (manager.firstname, manager.lastname)
                    continue
                
                # Get team members
                team_members = TeamMember.objects.filter(team=team).values_list('member', flat=True)
                team_members = RedmineUser.objects.filter(id__in=team_members)

                if team_members:
                    manager_name = "%s %s" % (manager.firstname, manager.lastname)
                    
                    entries = TimeEntry.objects.filter(
                        user__in=team_members,
                        spent_on__range=[start_date, end_date]
                    ).select_related('user', 'project', 'activity')

                    if entries.exists():
                        processed_entries = self.process_entries(entries)
                        
                        # Calculate total hours
                        total_hours = sum(entry.hours for entry in entries)
                        
                        context = {
                            'entries': processed_entries,
                            'start_date': start_date,
                            'end_date': end_date,
                            'monthly': options.get('monthly', False),
                            'supervisor_name': manager_name,
                            'total_hours': total_hours  # Add total hours to context
                        }

                        html_content = render_to_string('emails/supervisor_monthly_report.html', context)
                        subject = 'NDTL Team Manager %s Report (%s - %s)' % (
                            'Monthly' if options.get('monthly', False) else 'Weekly',
                            start_date.strftime('%b %d'),
                            end_date.strftime('%b %d')
                        )

                        # Send to test email without modifying subject
                        to_email = options.get('test_email') if options.get('test_email') else manager_email

                        self.send_notification(to_email, html_content, subject)
                        print "Sent report to %s" % to_email

        except Exception as e:
            print "Error: %s" % str(e)
            raise 