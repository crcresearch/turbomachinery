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

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sends weekly time reports to Supervisors'

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

    def get_report_dates(self, monthly=False, options=None):
        """Get start and end dates for the report period."""
        today = timezone.now().date()
        
        if options and (options.get('print') or options.get('test_email')):  # Add bypass for testing
            # For testing - bypass day-of-week check
            if monthly:
                start_date = today.replace(day=1)
                end_date = today
            else:
                # Get previous week (Saturday through Friday)
                end_date = today - timedelta(days=(today.weekday() + 3) % 7)  # Previous Friday
                start_date = end_date - timedelta(days=6)  # Previous Saturday
            return start_date, end_date
        
        # Production checks
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

        # Send the message via our own SMTP server
        s = smtplib.SMTP('dockerhost')
        s.sendmail('noreply@turbo.crc.nd.edu', list_of_recipients, msg.as_string())
        s.quit()

    def handle(self, *args, **options):
        start_date, end_date = self.get_report_dates(options.get('monthly', False), options)
        
        if not start_date or not end_date:
            if options.get('monthly'):
                print "Monthly reports should only run on the last Friday of the month"
            else:
                print "Weekly reports should only run on Mondays"
            return

        # Initialize HTML to text converter
        h = html2text.HTML2Text()
        h.body_width = 0  # Don't wrap text

        # Get all supervisors
        supervisors = Team.objects.all().select_related('manager')
        all_reports = {}

        for supervisor in supervisors:
            try:
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
                    supervisor_name = '%s %s (%s)' % (
                        supervisor.manager.firstname,
                        supervisor.manager.lastname,
                        email
                    )

                    if options['print']:
                        # Generate HTML content first
                        html_content = render_to_string('emails/supervisor_report.html', {
                            'supervisor_name': supervisor_name,
                            'start_date': start_date,
                            'end_date': end_date,
                            'report_data': report_data
                        })
                        
                        print "\n" + "="*80
                        print "Report for Supervisor: %s" % supervisor_name
                        print "="*80
                        print h.handle(html_content)  # Convert HTML to text table
                        print "="*80 + "\n"
                    else:
                        # Generate HTML content
                        html_content = render_to_string('emails/supervisor_report.html', {
                            'supervisor_name': supervisor_name,
                            'start_date': start_date,
                            'end_date': end_date,
                            'report_data': report_data
                        })

                        # Use test email if provided
                        recipient_email = options.get('test_email', email)

                        try:
                            self.send_notification(
                                recipient_email,
                                html_content,
                                'NDTL %s Time Report (%s - %s)' % (
                                    'Monthly' if options.get('monthly') else 'Weekly',
                                    start_date.strftime('%b %d'),
                                    end_date.strftime('%b %d')
                                )
                            )
                            print "Sent report to %s" % supervisor_name
                        except Exception as e:
                            logger.error("Failed to send email to %s: %s", supervisor_name, str(e))
                            print "Failed to send email to %s: %s" % (supervisor_name, str(e))

            except Exception as e:
                logger.error("Failed to process report for %s: %s", supervisor.manager.login, str(e))
                print "Failed to process report for %s: %s" % (supervisor.manager.login, str(e))

        print "Completed sending all supervisor reports" 