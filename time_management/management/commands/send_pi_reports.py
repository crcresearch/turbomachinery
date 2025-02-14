from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone
from django.db import connection
from django.core.mail import send_mail
from datetime import datetime, timedelta, date
from time_management.models import TimeEntry
import logging
import html2text
import re
import smtplib
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generates weekly time reports for Financial PIs'

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

    def is_email(self, string):
        """Check if string is an email address."""
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_regex, string) is not None

    def get_report_dates(self, monthly=False, options=None):
        """Get start and end dates for the report period."""
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

    def get_financial_pis_with_emails(self):
        """Get all Financial PIs and their email addresses."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT p.identifier, cv.value as financial_pi
                FROM projects p
                LEFT JOIN custom_values cv ON cv.customized_id = p.id
                LEFT JOIN custom_fields cf ON cf.id = cv.custom_field_id
                WHERE cf.name = 'Financial PI'
            """)
            return dict(cursor.fetchall())

    def get_financial_pi_projects(self, pi_name):
        """Get projects for a specific Financial PI."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT p.identifier
                FROM projects p
                LEFT JOIN custom_values cv ON cv.customized_id = p.id
                LEFT JOIN custom_fields cf ON cf.id = cv.custom_field_id
                WHERE cf.name = 'Financial PI'
                AND cv.value = %s
            """, [pi_name])
            return [row[0] for row in cursor.fetchall()]

    def generate_pi_report(self, entries):
        """Generate report data for a specific Financial PI."""
        pi_report = {
            'total_hours': 0.0,
            'projects': {}
        }

        for entry in entries:
            project_code = entry.project.identifier
            username = '%s %s' % (entry.user.firstname, entry.user.lastname)
            activity = entry.comments or (entry.activity.name if entry.activity else '')
            hours = float(entry.hours) if entry.hours else 0.0

            if project_code not in pi_report['projects']:
                pi_report['projects'][project_code] = {
                    'total_hours': 0.0,
                    'users': {}
                }

            if username not in pi_report['projects'][project_code]['users']:
                pi_report['projects'][project_code]['users'][username] = {
                    'hours': 0.0,
                    'activities': {}
                }

            if activity:
                if activity not in pi_report['projects'][project_code]['users'][username]['activities']:
                    pi_report['projects'][project_code]['users'][username]['activities'][activity] = {
                        'hours': hours
                    }
                else:
                    pi_report['projects'][project_code]['users'][username]['activities'][activity]['hours'] += hours

            pi_report['projects'][project_code]['users'][username]['hours'] += hours
            pi_report['projects'][project_code]['total_hours'] += hours
            pi_report['total_hours'] += hours

        # Sort projects
        pi_report['projects'] = dict(sorted(pi_report['projects'].items()))
        return pi_report

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
        # Get appropriate date range based on report type
        start_date, end_date = self.get_report_dates(options.get('monthly', False), options)
        
        if not start_date or not end_date:
            if options.get('monthly'):
                print "Monthly reports should only run on the last Friday of the month"
            else:
                print "Weekly reports should only run on Mondays"
            return

        # Get all Financial PIs
        financial_pis = self.get_financial_pis_with_emails()
        
        if not financial_pis:
            print "No Financial PIs found"
            return

        # Get unique PIs
        unique_pis = set(financial_pis.values())
        print "Found %d Financial PIs\n" % len(unique_pis)

        # Initialize HTML to text converter
        h = html2text.HTML2Text()
        h.body_width = 0  # Don't wrap text

        # Generate and send report for each unique PI
        for pi_name in unique_pis:
            try:
                # Get projects for this PI
                pi_projects = [proj_id for proj_id, pi in financial_pis.items() if pi == pi_name]
                
                if not pi_projects:
                    print "No projects found for PI: %s" % pi_name
                    continue

                # Get time entries for PI's projects
                entries = TimeEntry.objects.filter(
                    spent_on__range=[start_date, end_date],
                    hours__gt=0,
                    project__identifier__in=pi_projects
                ).select_related(
                    'project',
                    'user',
                    'activity'
                ).order_by(
                    'project__identifier',
                    'user__lastname',
                    'user__firstname'
                )

                if not entries:
                    print "No time entries found for PI: %s" % pi_name
                    continue

                # Generate report data
                report_data = self.generate_pi_report(entries)

                if options['print']:
                    # Print to console instead of sending email
                    print "\n" + "="*80
                    print "Report for PI: %s" % pi_name
                    print "="*80
                    print h.handle(html_content)
                    print "="*80 + "\n"
                    print "Generated report for %s" % pi_name
                else:
                    # Only send if test_email is provided or pi_name is an email
                    if options.get('test_email'):
                        recipient_email = options['test_email']
                    elif self.is_email(pi_name):
                        recipient_email = pi_name
                    else:
                        print "Skipping %s - not an email address" % pi_name
                        continue

                    # Generate HTML content
                    html_content = render_to_string('emails/weekly_report.html', {
                        'pi_name': pi_name,
                        'week_number': "%s-%s" % (str(start_date.strftime('%W')).zfill(2), str(end_date.strftime('%W')).zfill(2)),
                        'start_date': start_date.strftime('%b. %d, %Y'),
                        'end_date': end_date.strftime('%b. %d, %Y'),
                        'report_data': report_data
                    })

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
                        print "Sent report to %s" % pi_name
                    except Exception as e:
                        logger.error("Failed to send email to %s: %s", pi_name, str(e))
                        print "Failed to send email to %s: %s" % (pi_name, str(e))
                
            except Exception as e:
                logger.error("Failed to process report for %s: %s", pi_name, str(e))
                print "Failed to process report for %s: %s" % (pi_name, str(e))

        print "Completed generating all reports" 