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


class Command(BaseCommand):
    help = 'Sends out the daily reminder email to all users.'

    def handle(self, *args, **options):
        # load the template
        template_file = open('/opt/turbomachinery/templates/notification_emails/daily_reminder.html', 'r')
        email_content = template_file.read()

        # get a list of all users which have supervisors
        connection = psycopg2.connect(host='database1', database='redmine', user='postgres', password="Let's go turbo!")
        cursor = connection.cursor()

        cursor.execute("SELECT address FROM email_addresses;")
        addresses = cursor.fetchall()

        for address in addresses:
            print ("Sending to", address[0])
            msg = MIMEMultipart()
            msg['From'] = 'noreply@turbo.crc.nd.edu'
            msg['To'] = address[0]
            msg['Subject'] = 'Did you log your time in Redmine yesterday?'

            msg.attach(MIMEText(email_content, 'html'))

            smtp = smtplib.SMTP('dockerhost')
            smtp.sendmail('noreply@turbo.crc.nd.edu', address[0], msg.as_string())

            smtp.close()

        self.stdout.write(self.style.SUCCESS('Sent email of offending users. (%s users with low hours)' % len(addresses)))
