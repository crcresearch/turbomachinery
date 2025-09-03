from django.core.management.base import BaseCommand, CommandError
import datetime
import psycopg2
import csv
import os
import subprocess
# Import the email modules we'll need
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import COMMASPACE, formatdate
from email.mime.application import MIMEApplication
import smtplib


REPORT_TO_LIST = ['Beata.Nabrzyska.1@nd.edu']
#REPORT_TO_LIST = ['dpettifo@nd.edu']

class Command(BaseCommand):
    help = 'Generates a PDF report of individuals who fall under their minimum required hours and sends them out to the list of supervisors.'

    def handle(self, *args, **options):
        date_range = get_last_date_range()
        offenders = get_offending_users()
        if len(offenders) == 0:
            self.stdout.write(self.style.SUCCESS('Everyone had their hours in!'))
            return

        # get the offenders row template
        offender_template = open('/opt/turbomachinery/templates/reports/low_hours_row.tex', 'r')
        row_template = offender_template.read()
        offender_template.close()

        table_contents = """"""
        for offender in offenders:
            next_row = row_template.replace('{{ name }}', offender['name']).replace('{{ email }}', offender['email']).replace('{{ expected }}', str(offender['required'])).replace('{{ actual }}', str(offender['hours']))
            table_contents += next_row + '\n'

        # get the full tex document
        tex_template = open('/opt/turbomachinery/templates/reports/low_hours_template.tex', 'r')
        tex_contents = tex_template.read()
        tex_template.close()

        tex_contents = tex_contents.replace('{{ offenders_list }}', table_contents).replace('{{ timestamp }}', datetime.datetime.now().strftime('%B %d, %Y %H:%M:%S')).\
            replace('{{ current_date }}', datetime.datetime.now().strftime('%B %d, %Y')).\
            replace('{{ start_date }}', date_range['saturday'].strftime('%B %d, %Y')).\
            replace('{{ end_date }}', date_range['friday'].strftime('%B %d, %Y'))


        # Step 2: dump "content" to a local file
        #   Note: we use a timestamp so if multiple users generate SLAs at the same time,
        #           they won't collide with each other.
        file_name = os.path.join('/tmp/', 'Turbomachinery Redmine Low Hours Report')
        tex_file_name = file_name + '.tex'
        pdf_file_name = file_name + '.pdf'
        tex_file = open(tex_file_name, 'w')
        tex_file.write(tex_contents)
        tex_file.close()

        # Step 3: Generate our PDF using "pdflatex"
        #   Note: This requires the "texlive" package to be installed on the local machine
        p = subprocess.Popen(['pdflatex', '-output-directory', '/tmp', tex_file_name])
        p.wait()

        msg = MIMEMultipart()
        msg['From'] = 'noreply@turbo.crc.nd.edu'
        msg['To'] = COMMASPACE.join(REPORT_TO_LIST)
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = 'Turbomachinery Redmine Low-Hours Report'

        msg.attach(MIMEText(
            "Hello, please find the attached report of individuals with low hours for the previous work week. "))

        with open(pdf_file_name, "rb") as fil:
            part = MIMEApplication(
                fil.read(),
                Name=os.path.basename(pdf_file_name)
            )
        # After the file is closed
        part['Content-Disposition'] = 'attachment; filename="%s"' % os.path.basename(pdf_file_name)
        msg.attach(part)

        smtp = smtplib.SMTP('dockerhost')
        smtp.sendmail('noreply@turbo.crc.nd.edu', REPORT_TO_LIST, msg.as_string())

        smtp.close()

        self.stdout.write(self.style.SUCCESS('Sent email of offending users. (%s users with low hours)' % len(offenders)))


def get_offending_users():
    offending_users = []
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

    cursor.execute(
        "SELECT distinct(customized_id) FROM custom_values INNER JOIN users ON users.id = customized_id WHERE users.status = 1 and custom_field_id = %(custom_field_id)s;" % {
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
        cursor.execute(
            "SELECT id, default_value FROM custom_fields WHERE type = 'UserCustomField' and name = 'Minimum Weekly Hours Required';")
        min_hours_record = cursor.fetchone()

        cursor.execute(
            "SELECT value FROM custom_values WHERE custom_field_id = %(min_hours_id)s AND customized_id = %(user_id)s;" % {
                'user_id': user[0],
                'min_hours_id': min_hours_record[0]
            })
        users_requirements = cursor.fetchone()

        hours_required = int(min_hours_record[1])
        if users_requirements is not None:
            hours_required = int(users_requirements[0])

        # check hours
        if hours is None or hours < hours_required:
            cursor.execute("SELECT firstname, lastname FROM users WHERE id = %(user)s;" % {'user': user[0]})
            names = cursor.fetchone()

            cursor.execute(
                "SELECT address FROM email_addresses WHERE user_id = %(user)s AND is_default=TRUE LIMIT 1;" % {
                    'user': user[0]})
            email_address = cursor.fetchone()
            if email_address is not None:
                email_address = email_address[0]
            else:
                email_address = None

            offending_users.append({
                'name': names[0] + ' '+names[1],
                'email': email_address,
                'hours': hours,
                'required': hours_required
            })

    return offending_users



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
