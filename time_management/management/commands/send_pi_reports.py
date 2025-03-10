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
import psycopg2
import time  # Add at the top with other imports
from email.mime.multipart import MIMEMultipart

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

    def is_email(self, string):
        """Check if string is an email address."""
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_regex, string) is not None

    def get_report_dates(self, monthly=False, options=None):
        """Get start and end dates for the report period."""
        # If start_date and end_date are provided in options, use those
        if options and options.get('start_date') and options.get('end_date'):
            start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
            print("\nUsing provided dates: %s to %s" % (start_date, end_date))
            return start_date, end_date
        
        # Otherwise use default date logic
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

    def handle(self, *args, **options):
        print("\n=== Starting PI Report Generation ===")
        
        start_date, end_date = self.get_report_dates(options.get('monthly', False), options)
        print("\nDate Range: %s to %s" % (start_date, end_date))
        
        try:
            connection = psycopg2.connect(host='database1', database='redmine', user='postgres', password="Let's go turbo!")
            cursor = connection.cursor()
            
            # Get entries directly with all needed information
            cursor.execute("""
                SELECT 
                    cv.value as pi_name,
                    p.identifier as project_code,
                    u.firstname || ' ' || u.lastname as username,
                    te.comments,
                    a.name as activity_name,
                    te.hours,
                    te.spent_on
                FROM time_entries te
                JOIN projects p ON p.id = te.project_id
                JOIN users u ON u.id = te.user_id
                LEFT JOIN enumerations a ON a.id = te.activity_id
                LEFT JOIN custom_values cv ON cv.customized_id = p.id
                LEFT JOIN custom_fields cf ON cf.id = cv.custom_field_id
                WHERE cf.name = 'Financial PI'
                AND te.spent_on BETWEEN %s AND %s
                ORDER BY cv.value, p.identifier, u.lastname, u.firstname
            """, [start_date, end_date])
            
            entries = cursor.fetchall()
            print("\nFound %d entries" % len(entries))
            
            # Group entries by PI
            pi_data = {}
            for entry in entries:
                pi_name = entry[0]
                project_code = entry[1]
                username = entry[2]
                activity = entry[3] or entry[4] or 'No Activity'
                hours = float(entry[5])
                spent_date = entry[6]
                
                if pi_name not in pi_data:
                    pi_data[pi_name] = {'projects': {}}
                
                if project_code not in pi_data[pi_name]['projects']:
                    pi_data[pi_name]['projects'][project_code] = {
                        'total_hours': 0.0,
                        'users': {}
                    }
                
                if username not in pi_data[pi_name]['projects'][project_code]['users']:
                    pi_data[pi_name]['projects'][project_code]['users'][username] = {
                        'hours': 0.0,
                        'activities': {},
                        'dates': set()
                    }
                
                if activity not in pi_data[pi_name]['projects'][project_code]['users'][username]['activities']:
                    pi_data[pi_name]['projects'][project_code]['users'][username]['activities'][activity] = {
                        'hours': 0.0,
                        'dates': set()
                    }
                
                pi_data[pi_name]['projects'][project_code]['users'][username]['activities'][activity]['hours'] += hours
                pi_data[pi_name]['projects'][project_code]['users'][username]['activities'][activity]['dates'].add(spent_date)
                pi_data[pi_name]['projects'][project_code]['users'][username]['hours'] += hours
                pi_data[pi_name]['projects'][project_code]['total_hours'] += hours
                pi_data[pi_name]['projects'][project_code]['users'][username]['dates'].add(spent_date)
            
            # Process each PI's data
            for pi_name, data in pi_data.items():
                print("\nProcessing PI: %s" % pi_name)
                self.send_pi_report(pi_name, start_date, end_date, data['projects'], options)
            
        except Exception as e:
            print("ERROR: %s" % str(e))
            raise
        
        print("\n=== PI Report Generation Complete ===\n")

    def send_pi_report(self, pi_name, start_date, end_date, report_data, options):
        # Convert dates to strings
        for project_code in report_data:
            for username in report_data[project_code]['users']:
                dates = sorted(report_data[project_code]['users'][username]['dates'])
                report_data[project_code]['users'][username]['date_str'] = ', '.join(d.strftime('%m/%d') for d in dates)
                for activity in report_data[project_code]['users'][username]['activities']:
                    act_dates = sorted(report_data[project_code]['users'][username]['activities'][activity]['dates'])
                    report_data[project_code]['users'][username]['activities'][activity]['date_str'] = ', '.join(d.strftime('%m/%d') for d in act_dates)
        
        # Choose template based on report type
        template_name = 'emails/pi_monthly.html' if options.get('monthly') else 'emails/pi_weekly.html'
        
        if options.get('monthly'):
            # Group data by weeks for monthly report
            weekly_data = {}
            for project_code, project_data in report_data.items():
                for username, user_data in project_data['users'].items():
                    for date in user_data['dates']:
                        week_start = date - timedelta(days=date.weekday())
                        if week_start not in weekly_data:
                            weekly_data[week_start] = {}
                        if project_code not in weekly_data[week_start]:
                            weekly_data[week_start][project_code] = {
                                'total_hours': 0.0,
                                'users': {}
                            }
                        if username not in weekly_data[week_start][project_code]['users']:
                            weekly_data[week_start][project_code]['users'][username] = {
                                'hours': 0.0,
                                'activities': {},
                                'dates': set()
                            }
                        
                        # Copy activities for this week
                        for activity, activity_data in user_data['activities'].items():
                            if any(d.isocalendar()[1] == week_start.isocalendar()[1] for d in activity_data['dates']):
                                if activity not in weekly_data[week_start][project_code]['users'][username]['activities']:
                                    weekly_data[week_start][project_code]['users'][username]['activities'][activity] = {
                                        'hours': 0.0,
                                    }
                                weekly_data[week_start][project_code]['users'][username]['activities'][activity] = activity_data
                                weekly_data[week_start][project_code]['users'][username]['hours'] += activity_data['hours']
                                weekly_data[week_start][project_code]['total_hours'] += activity_data['hours']
                                weekly_data[week_start][project_code]['users'][username]['dates'].update(activity_data['dates'])
            
            context = {
                'pi_name': pi_name,
                'start_date': start_date,
                'end_date': end_date,
                'entries': [
                    {'week_start': week, 'list': data}
                    for week, data in sorted(weekly_data.items())
                ]
            }
        else:
            # Weekly report uses data as-is
            context = {
                'pi_name': pi_name,
                'start_date': start_date,
                'end_date': end_date,
                'report_data': report_data
            }
        
        html_content = render_to_string(template_name, context)
        
        if options.get('print') and not options.get('test_email'):
            print("\nReport Content for %s:" % pi_name)
            print(html_content)
        else:
            self.send_notification(
                options.get('test_email', pi_name),
                html_content,
                'NDTL Program %s Time Report (%s - %s)' % (
                    'Monthly' if options.get('monthly') else 'Weekly',
                    start_date.strftime('%b %d'),
                    end_date.strftime('%b %d')
                )
            )
            print("Sent report to %s" % (options.get('test_email', pi_name))) 