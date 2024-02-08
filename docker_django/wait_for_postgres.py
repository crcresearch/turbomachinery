#!/usr/bin/env python

import psycopg2
import sys
import time

# Default to offline (make that assumption)
offline = True

# Until it becomes online...
while offline:
    try:
        # try to connect!  we don't care if the password is right, we're just checking to see if we can get
        #   Postgres to answer us back...
        c = psycopg2.connect(host=sys.argv[1], database='postgres', user='postgres', password='invalid_password')

        # if the above didn't fail, then we actually got the password right (oops), but it means we're online
        offline = False
    except psycopg2.OperationalError as e:
        # If the "Connection refused", then we know Postgres isn't running on the expected host, so we wait 1 second
        # and try again
        if 'Connection refused' in str(e):
            print("PostgreSQL cannot be found...waiting 1 second and trying again...")
            offline = True
            time.sleep(1)
        else:
            # otherwise we probably got a password error of some sort, but it does mean we're online!
            offline = False
exit(0)