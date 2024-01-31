from django.core.management.base import BaseCommand, CommandError
import datetime
import psycopg2
import csv


class Command(BaseCommand):
    help = 'Imports and populates the supervisor list for each user from a known CSV.  Parameter usage: --csv=FILE.csv'

    def add_arguments(self, parser):
        parser.add_argument('--csv', type=str)

    def handle(self, *args, **options):
        # get a list of all users
        connection = psycopg2.connect(database='redmine_default', user='redmine_system', password='Lets go turbo!')
        cursor = connection.cursor()

        # get the custom field id for supervisor lists
        cursor.execute("SELECT id FROM custom_fields WHERE name = 'Supervisor Notification Emails' AND type='UserCustomField';")
        custom_field_id = cursor.fetchone()
        if custom_field_id is None:
            self.stdout.write(self.style.ERROR('Failed to find custom field "Supervisor Notification Emails" for users.'))
        else:
            custom_field_id = custom_field_id[0]

        # try to open the file
        try:
            csv_file = open(options['csv'], 'r')
        except IOError:
            self.stdout.write(self.style.ERROR('Unable to open file "%s"' % options['csv']))

        csv_contents = [{k: v for k, v in row.items()} for row in csv.DictReader(csv_file, skipinitialspace=True)]

        # loop through the contents of the CSV file, adding supervisors where we can
        total_adds = 0
        for row in csv_contents:
            # check for all three supervisors
            if row['Supervisor 1']:
                total_adds += add_supervisor_to_user(row['Login'], row['Supervisor 1'], custom_field_id, cursor)

            if row['Supervisor 2']:
                total_adds += add_supervisor_to_user(row['Login'], row['Supervisor 2'], custom_field_id, cursor)

            if row['Supervisor 3']:
                total_adds += add_supervisor_to_user(row['Login'], row['Supervisor 3'], custom_field_id, cursor)

        connection.commit()
        self.stdout.write(self.style.SUCCESS('Successfully added %s supervisor assignments.' % total_adds))


def add_supervisor_to_user(username, supervisor_email, custom_field_id, cursor):
    # make sure this doesn't already exist
    cursor.execute("SELECT COUNT(*) FROM custom_values "
                   "WHERE customized_id = "
                   "(SELECT id FROM users WHERE login = '%(username)s') "
                   "AND custom_field_id = %(custom_field_id)s "
                   "AND value = '%(supervisor_email)s';" % {
        'username': username,
        'supervisor_email': supervisor_email,
        'custom_field_id': custom_field_id
    })

    exists = cursor.fetchone()[0]

    if exists == 0:
        cursor.execute("INSERT INTO custom_values (customized_type, customized_id, custom_field_id, value) "
                       "VALUES "
                       "('Principal', "
                       "(SELECT id FROM users WHERE login = '%(username)s'), %(custom_field_id)s, "
                       "'%(supervisor_email)s');" % {
            'username': username,
            'supervisor_email': supervisor_email,
            'custom_field_id': custom_field_id
        })
        return 1
    else:
        print ("\t...skipped", username, " --> ", supervisor_email, "(already in system)")
        return 0