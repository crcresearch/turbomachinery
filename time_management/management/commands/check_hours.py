from django.core.management.base import BaseCommand, CommandError 
import datetime
import psycopg2
import smtplib
# Import the email modules we'll need
from email.mime.text import MIMEText
from django.shortcuts import render
from django.core.mail import send_mail


class Command(BaseCommand):
    help = 'Checks for low hours of the previous week'

    def add_arguments(self, parser):
        parser.add_argument('--type', type=str)

    def handle(self, *args, **options):
        dateframe = get_last_date_range()

        # get a list of all users which have supervisors
        connection = psycopg2.connect(
            host=os.environ.get('POSTGRES_HOST'), 
            database=os.environ.get('POSTGRES_DB'), 
            user=os.environ.get('POSTGRES_USER'), 
            password=os.environ.get('POSTGRES_PASSWORD')
        )
        cursor = connection.cursor()

        # get the custom field id for supervisor lists
        cursor.execute(
            "SELECT id FROM custom_fields WHERE name = 'Supervisor Notification Emails' AND type='UserCustomField';")
        custom_field_id = cursor.fetchone()
        if custom_field_id is None:
            self.stdout.write(
                self.style.ERROR('Failed to find custom field "Supervisor Notification Emails" for users.'))
        else:
            custom_field_id = custom_field_id[0]



        cursor.execute("SELECT distinct(customized_id) FROM custom_values INNER JOIN users ON users.id = customized_id WHERE users.status = 1 and custom_field_id = %(custom_field_id)s;" % {
            'custom_field_id': custom_field_id
        })

        user_list = cursor.fetchall()
        low_hours_count = 0
        for user in user_list:
            # get a list of supervisors to CC this time
            cursor.execute(
                "SELECT value FROM custom_values WHERE customized_id = %(user_id)s AND custom_field_id = %(field_id)s;" % {
                    'user_id': user[0],
                    'field_id': custom_field_id
                })
            supervisors = cursor.fetchall()
            supervisor_list = []
            for supervisor in supervisors:
                if supervisor[0] != '':
                    supervisor_list.append(supervisor[0])

            if len(supervisor_list) == 0:
                continue

            hours = get_hours(user_id=user[0],
                              start_date=dateframe['saturday'],
                              end_date=dateframe['friday'],
                              cursor=cursor)

            # get the expected hours (first check if there is a value defined, otherwise use the default)
            cursor.execute("SELECT id, default_value FROM custom_fields WHERE type = 'UserCustomField' and name = 'Minimum Weekly Hours Required';")
            min_hours_record = cursor.fetchone()

            cursor.execute("SELECT value FROM custom_values WHERE custom_field_id = %(min_hours_id)s AND customized_id = %(user_id)s;" % {
                'user_id': user[0],
                'min_hours_id': min_hours_record[0]
            })
            users_requirements = cursor.fetchone()

            hours_required = int(min_hours_record[1])
            if users_requirements is not None:
                hours_required = int(users_requirements[0])

            # check hours
            if hours is None or hours < hours_required:
                low_hours_count += 1
                cursor.execute("SELECT address FROM email_addresses WHERE user_id = %(user)s AND is_default=TRUE LIMIT 1;" % {'user': user[0]})
                email_address = cursor.fetchone()
                if email_address is not None:
                    email_address = email_address[0]
                else:
                    continue
                # print "Sending email to", user[0], "for low hours:", hours

                if options['type'] == 'saturday_morning':
                    print "sending email to", email_address, "for", hours, "<", hours_required
                    print supervisor_list
                    message = open('/opt/turbomachinery/templates/notification_emails/saturday_morning.html', 'r').read()
                    send_notification(email_address, supervisor_list, message, 'Redmine: Low Hours Reminder')

                if options['type'] == 'monday_morning':
                    print "sending email to", email_address, "for", hours, "<", hours_required
                    print supervisor_list
                    message = open('/opt/turbomachinery/templates/notification_emails/monday_morning.html', 'r').read()
                    send_notification(email_address, supervisor_list, message, 'Redmine: Low Hours Reminder')

                if options['type'] == 'monday_afternoon':
                    print "sending email to", email_address, "for", hours, "<", hours_required
                    print supervisor_list
                    message = open('/opt/turbomachinery/templates/notification_emails/monday_afternoon.html', 'r').read()
                    send_notification(email_address, supervisor_list, message, 'Redmine: Low Hours Reminder')

                if options['type'] == 'tuesday_morning':
                    print "sending email to", email_address, "for", hours, "<", hours_required
                    print supervisor_list
                    message = open('/opt/turbomachinery/templates/notification_emails/tuesday_morning.html', 'r').read()
                    send_notification(email_address, supervisor_list, message, 'Redmine: Low Hours Reminder')

        # print low_hours_count, "/", len(user_list), "had low hours"
        self.stdout.write(self.style.SUCCESS(options['type']+' '+str(low_hours_count) + ' of '+str(len(user_list))+' had low hours.'''))


def get_last_date_range():
    today = datetime.date.today()
    idx = (today.weekday() + 2) % 7  # MON = 0, SUN = 6 -> SUN = 0 .. SAT = 6
    # print ("IDX: " + str(idx))
    sat = today - datetime.timedelta(idx + 7)
    fri = sat + datetime.timedelta(6)
    return {
        'saturday': sat,
        'friday': fri
    }

def get_hours(user_id, start_date, end_date, cursor):
    cursor.execute("SELECT SUM(hours) FROM time_entries "
                   "WHERE user_id=%(user)s AND spent_on >= '%(start)s' AND spent_on <= '%(end)s'" % {
        'user': user_id,
        'start': start_date,
        'end': end_date
    })

    return cursor.fetchone()[0]

def send_notification(to_email, cc_list, message_body, message_subject):    
    #if cc_list:
    #    to_list = [to_email] + cc_list
    #else:
    #    to_list  = [to_email]

    #send_email(
    #	message_subject,
    #	message_body,
    #	'noreply@turbo.crc.nd.edu',
    #	to_list,
    #	fail_silently=False
    #)
    msg = MIMEText(message_body, 'html')

    msg['Subject'] = message_subject
    msg['From'] = 'noreply@turbo.crc.nd.edu'
    msg['To'] = to_email
    if cc_list:
        msg['Cc'] = ','.join(cc_list)
        list_of_recipients = [to_email] + cc_list
    else:
        list_of_recipients = [to_email]

    # Send the message via our own SMTP server, but don't include the
    # envelope header.
    s = smtplib.SMTP('dockerhost')
    s.sendmail('noreply@turbo.crc.nd.edu', list_of_recipients, msg.as_string())
    s.quit()
