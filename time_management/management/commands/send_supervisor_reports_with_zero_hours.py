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
import os
from email.mime.multipart import MIMEMultipart
from time import sleep

from time_management.models import Team

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generates weekly/monthly time reports for Supervisors (includes employees with zero hours)'

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
        
        try:
            smtp = smtplib.SMTP('dockerhost', timeout=10)
            smtp.sendmail('noreply@turbo.crc.nd.edu', [to_email], msg.as_string())
            smtp.close()
            time.sleep(60)  # Wait between emails
            return True
        except (smtplib.SMTPException, IOError, Exception) as e:
            print "Error sending email to %s: %s" % (to_email, str(e))
            return False

    def process_entries(self, entries, active_team_members=None):
        report_data = {}
        grand_total = 0
        project_totals = {}  # Track project totals
        
        # Initialize all active team members with zero hours
        if active_team_members is not None:
            for member in active_team_members:
                username = '%s %s' % (member.firstname, member.lastname)
                username = username.strip()
                if username not in report_data:
                    report_data[username] = {
                        'total_hours': 0,
                        'projects': {}
                    }
        
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

    def process_monthly_entries(self, entries, start_date, end_date, active_team_members=None):
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
        
        # Initialize all active team members with zero hours for all weeks
        if active_team_members is not None:
            for member in active_team_members:
                username = '%s %s' % (member.firstname, member.lastname)
                username = username.strip()
                if username not in report_data:
                    report_data[username] = {
                        'projects': {},
                        'total_hours': 0,
                        'weekly_totals': {w[0]: 0 for w in week_ranges}
                    }
        
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

    def get_db_credentials(self):
        """Get database credentials"""
        credentials = {
            'POSTGRES_DB': os.environ.get('POSTGRES_DB'),
            'POSTGRES_USER': os.environ.get('POSTGRES_USER'),
            'POSTGRES_PASSWORD': os.environ.get('POSTGRES_PASSWORD')
        }
        return credentials

    def handle(self, *args, **options):
        print "\n=== Starting Team Manager Report Generation (with zero hours) ==="
        
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
                
                # Get team member IDs
                team_member_ids = TeamMember.objects.filter(team=team).values_list('member', flat=True)
                
                # Get active team members (full objects, filtered by status=1)
                if team_member_ids:
                    active_team_members = RedmineUser.objects.filter(
                        id__in=team_member_ids,
                        status=1  # Only active users
                    )
                else:
                    active_team_members = RedmineUser.objects.none()  # Empty queryset
                    print "  Warning: No team members found for this team"
                
                # Get time entries for all team members
                entries = TimeEntry.objects.filter(
                    user__in=team_member_ids,
                    spent_on__range=[start_date, end_date]
                ).select_related('user', 'project', 'activity')

                # Always generate report if there are active team members (to show employees with zero hours)
                if not active_team_members.exists():
                    print "  Skipping: No active team members to report"
                    continue
                if options.get('monthly', False):
                    processed_data, week_numbers = self.process_monthly_entries(entries, start_date, end_date, active_team_members)
                    context = {
                        'entries': processed_data,
                        'week_numbers': week_numbers,
                        'start_date': start_date,
                        'end_date': end_date,
                        'monthly': True,
                        'supervisor_name': "%s %s" % (manager.firstname, manager.lastname)
                    }
                else:
                    processed_entries = self.process_entries(entries, active_team_members)
                    context = {
                        'entries': processed_entries,
                        'start_date': start_date,
                        'end_date': end_date,
                        'monthly': False,
                        'supervisor_name': "%s %s" % (manager.firstname, manager.lastname)
                    }

                html_content = render_to_string('emails/supervisor_monthly_report.html', context)
                subject = 'ND P&P Team Manager %s Report (%s - %s) [Includes Zero Hours]' % (
                    'Monthly' if options.get('monthly', False) else 'Weekly',
                    start_date.strftime('%b %d'),
                    end_date.strftime('%b %d')
                )

                # Check if --print flag is set
                if options.get('print'):
                    print "\n" + "="*80
                    print "REPORT FOR: %s %s" % (manager.firstname, manager.lastname)
                    print "SUBJECT: %s" % subject
                    print "="*80
                    print html_content
                    print "="*80 + "\n"
                else:
                    # Get manager's email
                    cursor = connection.cursor()
                    try:
                        cursor.execute("""
                            SELECT address 
                            FROM email_addresses 
                            WHERE user_id = %s 
                            AND is_default = true
                            LIMIT 1;
                        """, [manager.id])
                        result = cursor.fetchone()
                        manager_email = result[0] if result else None
                    finally:
                        cursor.close()
                    
                    if manager_email:
                        to_email = options.get('test_email') if options.get('test_email') else manager_email
                        if self.send_notification(to_email, html_content, subject):
                            print "Sent report to %s" % to_email
                        else:
                            print "Failed to send report to %s" % to_email
                    else:
                        print "No email found for manager %s %s - skipping report" % (manager.firstname, manager.lastname)

        except Exception as e:
            print "Error: %s" % str(e)
            raise

