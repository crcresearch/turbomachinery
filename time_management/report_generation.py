
from django.shortcuts import render, HttpResponse
from django.db import connection
import datetime
import calendar  # used for converting month integers to text
import csv
from time_management.costs import ServiceCost
from django.contrib.auth.decorators import login_required
from time_management.decorators import user_is_in_manager_group


class RedmineProject:
    def __init__(self, project_id=0, name='', parent_id=-1, fopal='', pi_name=''):
        self.id = project_id
        self.name = name
        self.parent_id = parent_id
        self.fopal = fopal
        self.pi_name = pi_name

    def __repr__(self):
        return self.name + ' (' + str(self.id) + ')'


def get_children(input_parent_id):
    """
    Recursive function that returns a list of children (and their children, and their children, etc) of
    the parent_id passed in
    """

    # connect to our database
    cur = connection.cursor()

    # prepare a list to add
    children_list = []

    # gather a list of all projects where the parent_id matches the one being passed in...
    cur.execute("SELECT id, \"name\" FROM projects WHERE parent_id = %(parent_id)s ORDER BY \"name\";" % {
        'parent_id': input_parent_id})
    children = cur.fetchall()

    if len(children) == 0:
        return children_list

    # otherwise, loop through all children and get their children!
    for child in children:
        cur.execute(
            "SELECT value FROM custom_values WHERE customized_id = %(project)s AND customized_type='Project' "
            "AND custom_field_id = 4" % {
                'project': child[0]})
        fopal = cur.fetchone()
        if fopal is not None:
            fopal = fopal[0]
        else:
            fopal = ''

        # get financial pi list
        cur.execute(
            'SELECT value FROM custom_values WHERE custom_field_id = 10 AND customized_id = %(project)s '
            'AND customized_type = \'Project\';' % {
                'project': child[0]})
        fpi = cur.fetchall()
        if len(fpi) >= 1:
            try:
                fpi = fpi[0][0]
                sfpi = fpi.split(' ')
                fpi = sfpi[1] + ', ' + sfpi[0]
            except:
                fpi = ''
        else:
            fpi = ''

        # create a child RedmineProject object
        new_child = RedmineProject(id=child[0], name=child[1], parent_id=input_parent_id, fopal=fopal, pi_name=fpi)
        children_list.append(new_child)
        # find all of this child's children
        children_list += get_children(child[0])

    # return our list!
    return children_list


def clean_fopal(fopal=''):
    # check to see if we have "XXXXX" in our FOPAL, if so, remove it and all white spaces
    if fopal == '':
        return fopal

    try:
        fopal = fopal.replace('XXXXX', "").replace(' ', "")
        return fopal
    except ValueError:
        return fopal


def check_fopal(fopal=''):
    try:
        float(fopal)
        return True
    except ValueError:
        return False


@login_required
@user_is_in_manager_group
def report_generator_home(request):
    # connect to our database
    cur = connection.cursor()

    # gather a list of all projects
    cur.execute(
        "SELECT projects.id, projects.name "
        "FROM projects "
        "INNER JOIN custom_values ON customized_id = projects.id "
        "INNER JOIN custom_fields ON custom_fields.id = custom_values.custom_field_id "
        "WHERE custom_fields.name = 'CORES Ready' "
        "AND custom_values.value = '1';")

    dbprojects = cur.fetchall()

    # total list of projects
    projects = []

    # run through all projects, adding them to the list (as RedmineProject objects)
    for project in dbprojects:
        # get the fopal for this project
        cur.execute(
            "SELECT value FROM custom_values "
            "inner join custom_fields on custom_fields.id = custom_values.custom_field_id "
            "WHERE customized_id = %(project)s and customized_type='Project' AND custom_fields.name = 'FOPAL';" % {
                'project': project[0]})
        fopal = cur.fetchone()[0]

        # get the financially responsible PI (if any)
        cur.execute(
            "SELECT value FROM custom_values "
            "inner join custom_fields on custom_fields.id = custom_values.custom_field_id "
            "WHERE customized_id = %(project)s and customized_type='Project' "
            "AND lower(custom_fields.name) = lower('Financial PI');" % {
                'project': project[0]})
        fpi = cur.fetchall()
        if len(fpi) >= 1:
            try:
                fpi = fpi[0][0]
                if len(fpi.split(' ')) > 1:
                    sfpi = fpi.split(' ')
                    fpi = sfpi[1] + ', ' + sfpi[0]
            except:
                fpi = ''
        else:
            fpi = ''

        new_proj = RedmineProject(project_id=project[0], name=project[1], fopal=fopal, pi_name=fpi)
        projects.append(new_proj)

    # prepare list for filtering
    required_list = '('
    for project_one in projects:
        project_id = project_one.id
        required_list += str(project_id) + ','
    if len(projects) > 0:
        required_list = required_list[:-1]
    else:
        required_list += 'NULL'
    required_list += ')'
    print (required_list)

    # gather a summation of all un-accounted hours that are not part of any of the projects we have listed
    today = datetime.date.today()
    first = datetime.date(day=1, month=today.month, year=today.year)
    lastMonth = first - datetime.timedelta(days=1)
    cur.execute(
        'SELECT SUM(hours), projects.name, projects.id FROM time_entries INNER JOIN users '
        'ON time_entries.user_id = users.id INNER JOIN projects ON time_entries.project_id=projects.id '
        'INNER JOIN enumerations ON enumerations.id=time_entries.activity_id '
        'INNER JOIN custom_values ON custom_values.customized_id = time_entries.id '
        'WHERE enumerations.name <> \'  Support (non-billable) \' AND custom_values.value '
        'NOT LIKE \'%%(external)%%\' AND time_entries.project_id NOT IN %(list)s '
        'AND tmonth = %(month)s AND tyear = %(year)s GROUP BY projects.id, projects.name;' % {
            'month': lastMonth.strftime('%m'), 'year': lastMonth.strftime('%Y'), 'list': required_list})
    missing_hours = cur.fetchall()

    # gather a list of all years
    cur.execute("SELECT DISTINCT tyear FROM time_entries ORDER BY tyear;")
    dbyears = cur.fetchall()

    # gather a list of all months (should always be 1-12)
    cur.execute("SELECT DISTINCT tmonth FROM time_entries ORDER BY tmonth;")
    dbmonths = cur.fetchall()

    # close our database connection
    connection.close()

    # loop through, constructing our projects as dictionaries
    project_list = []
    for project in projects:
        new_proj = {}
        new_proj['id'] = project.id
        new_proj['name'] = project.name
        new_proj['parent'] = project.parent_id
        new_proj['fopal'] = clean_fopal(project.fopal)
        if project.fopal != '' and check_fopal(new_proj['fopal']) is False:
            new_proj['error'] = 'Incorrectly formatted FOPAL'
        else:
            new_proj['error'] = ''
        if project.pi_name == '' and project.fopal != '':
            if new_proj['error'] != '':
                new_proj['error'] += ', '
            new_proj['error'] += 'Missing Financial PI name'
        new_proj['pi'] = project.pi_name
        project_list.append(new_proj)

    # loop through unassigned hours, creating a dictionary of unaccounted hours
    missing_list = []
    total_missing = 0
    for project in missing_hours:
        new_proj = {}
        new_proj['name'] = project[1]
        new_proj['id'] = project[2]
        new_proj['hours'] = project[0]
        total_missing += project[0]
        missing_list.append(new_proj)

    # loop through the years, constructing a year dictionary
    year_list = []
    for year in dbyears:
        new_year = {}  # haha...new year...
        new_year['year'] = year[0]
        year_list.append(new_year)

    # loop through the months, constructing a month dictionary
    month_list = []
    for month in dbmonths:
        new_month = {}
        new_month['number'] = month[0]
        new_month['name'] = calendar.month_name[month[0]]
        month_list.append(new_month)

    # generate our context to pass through
    start_date = str(datetime.datetime.now().today().month) + '/1/'+str(datetime.datetime.now().today().year)
    end_date = datetime.datetime.now().today().strftime('%m/%d/%Y')
    context = {'projects': project_list, 'years': year_list, 'months': month_list, 'missing_hours': total_missing,
               'missing_list': missing_list, 'start': start_date, 'end': end_date}

    return render(request, 'report_generator.html', context)


@login_required
@user_is_in_manager_group
def generate_internal_report(request):
    # Top line - column headers
    header = ['Primary Comments', 'Customer Account Number', 'Core Account Number', 'Service Date', 'Service Description', 'Quantity',
              'Unit', 'Price', 'Service Category', 'Secondary Comments', 'PI\'s Name', 'Purchaser\'s Last Name',
              'Short Contributing Billing Name', 'Resource Name', 'Line Item Assistant', 'Line Item Comments',
              'Project ID']

    project_list = request.GET['ProjectList'].replace('"', '').split(',')

    # create a CSV response type
    response = HttpResponse(content_type='text/csv')

    # give it a file name of "RedmineReport.csv"
    response['Content-Disposition'] = 'attachment; filename="RedmineReport.csv"'

    # create the writer
    writer = csv.writer(response)

    # write the first row (header)
    writer.writerow(header)

    # connect to our database
    cur = connection.cursor()

    # prepare list for filtering
    required_list = '('
    for project in project_list:
        required_list += project + ','
    required_list = required_list[:-1] + ')'

    print (required_list)
    print (len(required_list.split(',')))

    # NOTE: Here is an explination of what should be gathered:
    #  Primary Comments: 		Project Name
    #  Customer Account Number: 	FOPAL
    #  Transaction Date:		Date
    #  Service Description:		Computational Scientist Services, GIS/Visualization Services, HPC Services,
    #                           Programming, Graduate Course, HS/Community, Other, Undergrad Course
    #  Quantity:			Number of hours/month
    #  Unit:			Hour
    #  Price:			Hourly Rate
    #  Service Category:		CS, GIS/Vis, HPC, Outreach, Programming, etc.
    #  Secondary Comments:		None
    #  PI's Name:			Financially Responsible PI
    #  Purchaser's Last Name:	PI on the project
    #  Short Contrib...:		None
    #  Resource Name:		None
    #  Line Item Assistant:		NetID of user
    #  Line Item Comments:		None

    print (len(project_list[0]))

    if len(project_list[0]) != 0:
        # for each project in our list, gather all of the data we need!
        for project in project_list:
            # first, check if there are any logged hours for this project that are part of the CSR
            cur.execute("select sum(hours) from time_entries "
                        " inner join custom_values ON custom_values.customized_id = time_entries.id "
                        " inner join charge_rates ON custom_values.value = charge_rates.category"
                        " where custom_values.customized_type = 'TimeEntry'"
                        " and time_entries.project_id = %(project_id)s;" % {'project_id': project})
            hours = cur.fetchone()

            # print "HOURS for", project, ":", hours
            if len(hours) == 1 and hours[0] is None:
                continue

            cur.execute('SELECT "name" FROM projects WHERE id=%(id)s;' % {'id': project})
            project_name = cur.fetchall()[0][0]

            # get the project FOPAL
            cur.execute(
                "SELECT value FROM custom_values "
                "inner join custom_fields on custom_fields.id = custom_values.custom_field_id "
                "WHERE customized_id = %(project)s and customized_type='Project' AND custom_fields.name = 'FOPAL';" % {
                    'project': project})
            fopal = cur.fetchall()
            if len(fopal) >= 1:
                fopal = fopal[0][0]
            else:
                fopal = ''

            # get the financially responsible PI (if any)
            cur.execute(
                "SELECT value FROM custom_values "
                "inner join custom_fields on custom_fields.id = custom_values.custom_field_id "
                "WHERE customized_id = %(project)s and customized_type='Project' "
                "AND lower(custom_fields.name) = lower('Financial PI');" % {
                    'project': project})
            fpi = cur.fetchall()
            if len(fpi) >= 1:
                try:
                    fpi = fpi[0][0]
                    sfpi = fpi.split(' ')
                    fpi = sfpi[1] + ', ' + sfpi[0]
                except:
                    pass
            else:
                fpi = ''

            # get the PI list
            cur.execute(
                "SELECT value FROM custom_values "
                "inner join custom_fields on custom_fields.id = custom_values.custom_field_id "
                "WHERE customized_id = %(project)s and customized_type='Project' "
                "AND lower(custom_fields.name) = lower('PI');" % {
                    'project': project})
            pi = cur.fetchall()
            if len(pi) >= 1:
                pi = pi[0][0]
            else:
                pi = ''

            # get the total time spent for each individual, and for each billing type
            cur.execute(
                "select sum(hours), users.firstname, users.lastname, custom_values.value, users.login, time_entries.spent_on "
                "from time_entries "
                "inner join users on users.id = time_entries.user_id "
                "inner join custom_values ON custom_values.customized_id = time_entries.id "
                "inner join custom_fields on custom_fields.id = custom_values.custom_field_id "
                "inner join projects on projects.id = time_entries.project_id "
                "inner join enumerations on enumerations.id = time_entries.activity_id "
                "where (time_entries.project_id = %(project_id)s ) "
                "and custom_values.value != '' "
                "and time_entries.spent_on >= '%(start)s'::date and time_entries.spent_on <= '%(end)s'::date "
                "and lower(enumerations.name) not like '%%non%%billable' "
                "group by users.firstname, users.lastname, users.login, custom_values.value, time_entries.spent_on "
                "order by users.lastname;" % {'project_id': project, 'start': request.GET['start'],
                                              'end': request.GET['end']})

            times = cur.fetchall()
            print("TIMES:", times)
            # print times
            # format of the "times":
            # times[0] = summation of hours
            # times[1] = last name
            # times[2] = first name
            # times[3] = activity
            # times[4] = login/username
            # times[5] = date of time entry (used for referencing cost)

            # get the last day of the range
            day = request.GET['end'] #calendar.monthrange(int(request.GET['year']), int(request.GET['month']))[1]

            # loop through all time records, creating a new row of information to add
            records = []
            for record in times:
                # grab the rate for the date we're working with, along with the cores display name
                internal = 'TRUE'
                if 'external' in record[3]:
                    internal = 'FALSE'
                query = "SELECT rate, cores_display FROM charge_rates WHERE '%(date)s'::date >= start_date " \
                        "AND '%(date)s'::date <= end_date AND category = '%(category)s' " % {
                            'date': record[5], 'category': record[3]}
                try:
                    cur.execute(query)
                    rate_info = cur.fetchone()
                    # print "Record:", record,
                    # print "Rate:", rate_info
                    if rate_info is None:
                        # then assume rate is 0
                        rate = 0
                        cores_display = record[3]
                    else:
                        rate = rate_info[0]
                        cores_display = rate_info[1]

                except:
                    return HttpResponse(
                        "An error occured internally.  Please send an email to dpettifo@nd.edu and paste the "
                        "following into the email: <br> " + query)
                new_record = {}
                new_record['name'] = project_name  # Primary Comments
                new_record['fopal'] = '"'+clean_fopal(fopal) + '"'  # Customer Account Number
                new_record['core_account_number'] = '3900314333340000' # Core Account Number (static for Turbo)

                new_record['trans'] = day  # Transaction Date
                new_record['service'] = cores_display  # (cost_lib.getCORESName(record[3]))		# Service Description
                new_record['hours'] = record[0]  # Quantity (Hours)
                new_record['unit'] = 'Hour'  # Unit (hours)
                new_record['rate'] = str(rate)  # Hourly rate
                new_record['category'] = cores_display  # (cost_lib.getCORESName(record[3]))		# Service Category
                new_record['secondary_comments'] = '"' + record[2] + ' ' + record[
                    1] + '"'  # Secondary comments (always empty?)
                new_record['fpi'] = (pi)  # Financially responsible PI (formatted as: "Last,First MI")
                new_record['pi'] = '"' + fpi + '"'  # Purchasers Last Name (PI we're working with)
                new_record['center'] = '""'  # Short Contributing Center Name
                new_record['resource'] = '""'  # Resource Name
                new_record['login'] = '"' + record[4] + '"'  # Line Item Assistant (netID of the user)
                new_record['comment'] = '"' + record[2] + ' ' + record[1] + '"'  # Line Item Comment
                new_record['project_id'] = '""' # Always blank

                # do we already have this record?
                added = False
                for rec in records:
                    if rec['name'] == new_record['name'] and rec['service'] == new_record['service'] \
                            and rec['rate'] == new_record['rate'] and rec['login'] == new_record['login'] \
                            and rec['trans'] == new_record['trans']:
                        rec['hours'] += new_record['hours']
                        added = True
                if not added:
                    records.append(new_record)

            # now loop through the collective rows, and write them
            for record in records:
                new_record = []
                new_record.append(record['name'])
                new_record.append(record['fopal'])
                new_record.append(record['core_account_number'])
                new_record.append(record['trans'])
                new_record.append(record['service'])
                new_record.append(record['hours'])
                new_record.append(record['unit'])
                new_record.append(record['rate'])
                new_record.append(record['category'])
                new_record.append(record['secondary_comments'])
                new_record.append(record['fpi'])
                new_record.append(record['pi'])
                new_record.append(record['center'])
                new_record.append(record['resource'])
                new_record.append(record['login'])
                new_record.append(record['comment'])
                new_record.append(record['project_id'])
                # write row!
                writer.writerow(new_record)

    return response



@login_required
@user_is_in_manager_group
def generate_csr_report(request):
    # Top line - column headers
    header = ['Primary Comments', 'Customer Account Number', 'Transaction Date', 'Service Description', 'Quantity',
              'Unit', 'Price', 'Service Category', 'Secondary Comments', 'PI\'s Name', 'Purchaser\'s Last Name',
              'Short Contributing Center Name', 'Resource Name', 'Line Item Assistant', 'Line Item Comments']

    project_list = request.GET['ProjectList'].replace('"', '').split(',')

    # create a CSV reponse type
    response = HttpResponse(content_type='text/csv')

    # give it a file name of "RedmineReport.csv"
    response['Content-Disposition'] = 'attachment; filename="RedmineReport.csv"'

    # create the writer
    writer = csv.writer(response)

    # write the first row (header)
    writer.writerow(header)

    # connect to our database
    cur = connection.cursor()

    # prepare list for filtering
    required_list = '('
    for project in project_list:
        required_list += project + ','
    required_list = required_list[:-1] + ')'

    # NOTE: Here is an explination of what should be gathered:
    #  Primary Comments: 		Project Name
    #  Customer Account Number: 	FOPAL
    #  Transaction Date:		Date
    #  Service Description:		Computational Scientist Services, GIS/Visualization Services, HPC Services,
    #                           Programming, Graduate Course, HS/Community, Other, Undergrad Course
    #  Quantity:			Number of hours/month
    #  Unit:			Hour
    #  Price:			Hourly Rate
    #  Service Category:		CS, GIS/Vis, HPC, Outreach, Programming, etc.
    #  Secondary Comments:		None
    #  PI's Name:			Financially Responsible PI
    #  Purchaser's Last Name:	PI on the project
    #  Short Contrib...:		None
    #  Resource Name:		None
    #  Line Item Assistant:		NetID of user
    #  Line Item Comments:		None

    # print len(project_list[0])

    if len(project_list[0]) != 0:
        # for each project in our list, gather all of the data we need!
        for project in project_list:
            # first, check if there are any logged hours for this project that are part of the CSR
            cur.execute("select sum(hours) from time_entries "
                        " inner join custom_values ON custom_values.customized_id = time_entries.id "
                        " inner join charge_rates ON charge_rates.category = custom_values.value"
                        " inner join center ON charge_rates.center = center.id"
                        " where custom_values.customized_type = 'TimeEntry'"
                        " and center.name = 'Center for Social Research'"
                        " and time_entries.project_id = %(project_id)s;" % {'project_id': project})
            hours = cur.fetchone()
            if len(hours) == 1 and hours[0] is None:
                continue

            # get the project name
            cur.execute('SELECT "name" FROM projects WHERE id=%(id)s;' % {'id': project})
            project_name = cur.fetchall()[0][0]

            # get the project FOPAL
            cur.execute(
                'SELECT value FROM custom_values WHERE custom_field_id = 4 '
                'AND customized_id = %(project)s AND customized_type = \'Project\';' % {
                    'project': project})
            fopal = cur.fetchall()
            if len(fopal) >= 1:
                fopal = fopal[0][0]
            else:
                fopal = ''

            # get the financially responsible PI (if any)
            cur.execute(
                'SELECT value FROM custom_values WHERE custom_field_id = 10 '
                'AND customized_id = %(project)s AND customized_type = \'Project\';' % {
                    'project': project})
            fpi = cur.fetchall()
            if len(fpi) >= 1:
                try:
                    fpi = fpi[0][0]
                    sfpi = fpi.split(' ')
                    fpi = sfpi[1] + ', ' + sfpi[0]
                except:
                    fpi = ''
            else:
                fpi = ''

            # get the PI list
            cur.execute(
                'SELECT value FROM custom_values WHERE custom_field_id = 6 '
                'AND customized_id = %(project)s AND customized_type = \'Project\';' % {
                    'project': project})
            pi = cur.fetchall()
            if len(pi) >= 1:
                pi = pi[0][0]
            else:
                pi = ''

            # get the total time spent for each individual, and for each billing type
            cur.execute(
                'SELECT SUM(hours), users.lastname, users.firstname, custom_values.value, '
                'users.login, time_entries.spent_on '
                'FROM time_entries '
                'INNER JOIN users ON time_entries.user_id=users.id '
                'INNER JOIN projects ON time_entries.project_id=projects.id '
                'INNER JOIN enumerations ON enumerations.id=time_entries.activity_id '
                'INNER JOIN custom_values ON custom_values.customized_id = time_entries.id'
                ' WHERE (time_entries.project_id = ANY(childlist(%(project_id)s)) '
                'OR time_entries.project_id = %(project_id)s)'
                ' AND enumerations.name <> \'  Support (non-billable) \' '
                'AND custom_values.value NOT LIKE \'%%(external)%%\' '
                'AND tmonth = %(month)s AND tyear = %(year)s '
                'AND time_entries.project_id IN %(list)s '
                'AND custom_values.value LIKE \'%%Statistical%%\''
                'GROUP BY users.lastname, users.firstname, users.login, custom_values.value, time_entries.spent_on '
                'ORDER BY users.lastname, users.firstname;' % {
                    'project_id': project, 'month': request.GET['month'], 'year': request.GET['year'],
                    'list': required_list})
            times = cur.fetchall()

            # format of the "times":
            # times[0] = summation of hours
            # times[1] = last name
            # times[2] = first name
            # times[3] = activity
            # times[4] = login/username
            # times[5] = date of time entry (used for referencing cost)

            # get the last day of the month
            day = calendar.monthrange(int(request.GET['year']), int(request.GET['month']))[1]

            # loop through all time records, creating a new row of information to add
            records = []
            for record in times:
                # grab the rate for the date we're working with, along with the cores display name
                internal = 'TRUE'
                if 'external' in record[3]:
                    internal = 'FALSE'
                query = "SELECT rate, cores_display FROM charge_rates WHERE '%(date)s'::date >= start_date " \
                        "AND '%(date)s'::date <= end_date AND category = '%(category)s' " \
                        "AND internal = %(internal)s;" % {
                            'date': record[5], 'category': record[3], 'internal': internal}
                try:
                    cur.execute(query)
                    rate_info = cur.fetchone()
                    rate = rate_info[0]
                    cores_display = rate_info[1]

                except:
                    return HttpResponse(
                        "An error occured internally.  Please send an email to dpettifo@nd.edu and "
                        "paste the following into the email: <br> " + query)
                new_record = {}
                new_record['name'] = project_name  # Primary Comments
                new_record['fopal'] = clean_fopal(fopal)  # Customer Account Number
                new_record['trans'] = (
                    str(day) + '-' + calendar.month_abbr[int(request.GET['month'])].upper() + '-' + request.GET['year'][
                                                                                                2:])  # Transaction Date
                new_record['service'] = cores_display  # (cost_lib.getCORESName(record[3]))		# Service Description
                new_record['hours'] = record[0]  # Quantity (Hours)
                new_record['unit'] = 'Hour'  # Unit (hours)
                new_record['rate'] = str(rate)  # Hourly rate
                new_record['category'] = cores_display  # (cost_lib.getCORESName(record[3]))		# Service Category
                new_record['secondary_comments'] = '"' + record[2] + ' ' + record[
                    1] + '"'  # Secondary comments (always empty?)
                new_record['fpi'] = '"' + fpi + '"'  # Financially responsible PI (formatted as: "Last,First MI")
                new_record['pi'] = (pi)  # Purchasers Last Name (PI we're working with)
                new_record['center'] = '""'  # Short Contributing Center Name
                new_record['resource'] = '""'  # Resource Name
                new_record['login'] = '"' + record[4] + '"'  # Line Item Assistant (netID of the user)
                new_record['comment'] = '"' + record[2] + ' ' + record[1] + '"'  # Line Item Comment

                # do we already have this record?
                added = False
                for rec in records:
                    if rec['name'] == new_record['name'] and rec['service'] == new_record['service'] \
                            and rec['rate'] == new_record['rate'] and rec['login'] == new_record['login'] \
                            and rec['trans'] == new_record['trans']:
                        rec['hours'] += new_record['hours']
                        added = True
                if not added:
                    records.append(new_record)

            # now loop through the collective rows, and write them
            for record in records:
                new_record = []
                new_record.append(record['name'])
                new_record.append(record['fopal'])
                new_record.append(record['trans'])
                new_record.append(record['service'])
                new_record.append(record['hours'])
                new_record.append(record['unit'])
                new_record.append(record['rate'])
                new_record.append(record['category'])
                new_record.append(record['secondary_comments'])
                new_record.append(record['fpi'])
                new_record.append(record['pi'])
                new_record.append(record['center'])
                new_record.append(record['resource'])
                new_record.append(record['login'])
                new_record.append(record['comment'])
                # write row!
                writer.writerow(new_record)

    return response



@login_required
@user_is_in_manager_group
def generate_external_report(request):
    # Top line - column headers
    header = ['Primary Comments', 'Customer Account Number', 'Transaction Date', 'Service Description', 'Quantity',
              'Unit', 'Price', 'Service Category', 'Secondary Comments', 'PI\'s Name', 'Purchaser\'s Last Name',
              'Short Contributing Center Name', 'Resource Name', 'Line Item Assistant', 'Line Item Comments']

    project_list = request.GET['ProjectList'][1:-1].replace('"', '').split(',')

    # create a CSV response type
    response = HttpResponse(content_type='text/csv')

    # give it a file name of "RedmineReport.csv"
    response['Content-Disposition'] = 'attachment; filename="RedmineReport.csv"'

    # create the writer
    writer = csv.writer(response)

    # write the first row (header)
    writer.writerow(header)

    # connect to our database
    cur = connection.cursor()

    # grab all of our costs while we're at it
    cost_lib = ServiceCost()

    # prepare list for filtering
    required_list = '('
    for project in project_list:
        required_list += project + ','
    required_list = required_list[:-1] + ')'

    # NOTE: Here is an explination of what should be gathered:
    #  Primary Comments: 		Project Name
    #  Customer Account Number: 	FOPAL
    #  Transaction Date:		Date
    #  Service Description:		Computational Scientist Services, GIS/Visualization Services, HPC Services,
    #                           Programming, Graduate Course, HS/Community, Other, Undergrad Course
    #  Quantity:			Number of hours/month
    #  Unit:			Hour
    #  Price:			Hourly Rate
    #  Service Category:		CS, GIS/Vis, HPC, Outreach, Programming, etc.
    #  Secondary Comments:		None
    #  PI's Name:			Financially Responsible PI
    #  Purchaser's Last Name:	PI on the project
    #  Short Contrib...:		None
    #  Resource Name:		None
    #  Line Item Assistant:		NetID of user
    #  Line Item Comments:		None

    print (len(project_list[0]))

    if len(project_list[0]) != 0:
        # for each project in our list, gather all of the data we need!
        for project in project_list:
            # first check to see if this is a child project and if so, check if the parent is in the list.
            # If that is true, then abort!
            cur.execute('SELECT parent_id FROM projects WHERE id=%(project)s;' % {'project': project})
            parent_id = cur.fetchone()[0]

            found = False
            for parent in project_list:
                # add exception for HPC parent project
                if str(parent_id) == str(parent):
                    print ('Found in list...skipping')
                    found = True
            if found:
                continue
            # get the project name
            cur.execute('SELECT "name" FROM projects WHERE id=%(id)s;' % {'id': project})
            project_name = cur.fetchall()[0][0]

            # get the project FOPAL
            cur.execute(
                'SELECT value FROM custom_values WHERE custom_field_id = 4 AND customized_id = %(project)s '
                'AND customized_type = \'Project\';' % {
                    'project': project})
            fopal = cur.fetchall()
            if len(fopal) >= 1:
                fopal = fopal[0][0]
            else:
                fopal = ''

            # get the financially responsible PI (if any)
            cur.execute(
                'SELECT value FROM custom_values WHERE custom_field_id = 10 AND customized_id = %(project)s '
                'AND customized_type = \'Project\';' % {
                    'project': project})
            fpi = cur.fetchall()
            if len(fpi) >= 1:
                try:
                    fpi = fpi[0][0]
                    sfpi = fpi.split(' ')
                    fpi = sfpi[1] + ', ' + sfpi[0]
                except:
                    fpi = ''
            else:
                fpi = ''

            # get the PI list
            cur.execute(
                'SELECT value FROM custom_values WHERE custom_field_id = 6 AND customized_id = %(project)s '
                'AND customized_type = \'Project\';' % {
                    'project': project})
            pi = cur.fetchall()
            if len(pi) >= 1:
                pi = pi[0][0]
            else:
                pi = ''

            # get the total time spent for each individual, and for each billing type
            cur.execute(
                'SELECT SUM(hours), users.lastname, users.firstname, custom_values.value, users.login, '
                'time_entries.spent_on FROM time_entries INNER JOIN users ON time_entries.user_id=users.id '
                'INNER JOIN projects ON time_entries.project_id=projects.id INNER JOIN enumerations '
                'ON enumerations.id=time_entries.activity_id INNER JOIN custom_values '
                'ON custom_values.customized_id = time_entries.id WHERE (time_entries.project_id = '
                'ANY(childlist(%(project_id)s)) OR time_entries.project_id = %(project_id)s) '
                'AND enumerations.name <> \'  Support (non-billable) \' AND custom_values.value '
                'NOT LIKE \'%%(internal)%%\' AND tmonth = %(month)s AND tyear = %(year)s AND time_entries.project_id '
                'IN %(list)s GROUP BY users.lastname, users.firstname, users.login, custom_values.value, '
                'time_entries.spent_on ORDER BY users.lastname, users.firstname;' % {
                    'project_id': project, 'month': request.GET['month'], 'year': request.GET['year'],
                    'list': required_list})
            times = cur.fetchall()

            # format of the "times":
            # times[0] = summation of hours
            # times[1] = last name
            # times[2] = first name
            # times[3] = activity
            # times[4] = login/username
            # times[5] = date of time entry (used for referencing cost)

            # get the last day of the month
            day = calendar.monthrange(int(request.GET['year']), int(request.GET['month']))[1]

            # loop through all time records, creating a new row of information to add
            records = []
            for record in times:
                # grab the rate for the date we're working with, along with the cores display name
                internal = 'TRUE'
                if 'external' in record[3]:
                    internal = 'FALSE'
                query = "SELECT rate, cores_display FROM charge_rates WHERE '%(date)s'::date >= start_date " \
                        "AND '%(date)s'::date <= end_date AND category = '%(category)s' " \
                        "AND internal = %(internal)s;" % {
                            'date': record[5], 'category': record[3].split(' ')[0], 'internal': internal}
                try:
                    cur.execute(query)
                    rate_info = cur.fetchone()
                    rate = rate_info[0]
                    cores_display = rate_info[1]

                except:
                    return HttpResponse(
                        "An error occured internally.  Please send an email to dpettifo@nd.edu and paste the "
                        "following into the email: <br> " + query)
                new_record = {}
                new_record['name'] = project_name  # Primary Comments
                new_record['fopal'] = clean_fopal(fopal)  # Customer Account Number
                new_record['trans'] = (
                    str(day) + '-' + calendar.month_abbr[int(request.GET['month'])].upper() + '-' + request.GET['year'][
                                                                                                2:])  # Transaction Date
                new_record['service'] = cores_display  # (cost_lib.getCORESName(record[3]))		# Service Description
                new_record['hours'] = record[0]  # Quantity (Hours)
                new_record['unit'] = 'Hour'  # Unit (hours)
                new_record['rate'] = str(rate)  # Hourly rate
                new_record['category'] = cores_display  # (cost_lib.getCORESName(record[3]))		# Service Category
                new_record['secondary_comments'] = '""'  # Secondary comments (always empty?)
                new_record['fpi'] = '"' + fpi + '"'  # Financially responsible PI (formatted as: "Last,First MI")
                new_record['pi'] = (pi)  # Purchasers Last Name (PI we're working with)
                new_record['center'] = '""'  # Short Contributing Center Name
                new_record['resource'] = '""'  # Resource Name
                new_record['login'] = '"' + record[4] + '"'  # Line Item Assistant (netID of the user)
                new_record['comment'] = '""'  # Line Item Comment

                # do we already have this record?
                added = False
                for rec in records:
                    if rec['name'] == new_record['name'] and rec['service'] == new_record['service'] \
                            and rec['rate'] == new_record['rate'] and rec['login'] == new_record['login'] \
                            and rec['trans'] == new_record['trans']:
                        rec['hours'] += new_record['hours']
                        added = True
                if not added:
                    records.append(new_record)

            # now loop through the collective rows, and write them
            for record in records:
                new_record = []
                new_record.append(record['name'])
                new_record.append(record['fopal'])
                new_record.append(record['trans'])
                new_record.append(record['service'])
                new_record.append(record['hours'])
                new_record.append(record['unit'])
                new_record.append(record['rate'])
                new_record.append(record['category'])
                new_record.append(record['secondary_comments'])
                new_record.append(record['fpi'])
                new_record.append(record['pi'])
                new_record.append(record['center'])
                new_record.append(record['resource'])
                new_record.append(record['login'])
                new_record.append(record['comment'])
                # write row!
                writer.writerow(new_record)

    # now get all of the unassigned hours and add these to the CSV
    if request.GET['all_projects'] == 'checked':
        cur.execute(
            "SELECT SUM(hours), users.lastname, users.firstname, custom_values.value, users.login, projects.name "
            "FROM time_entries INNER JOIN users ON time_entries.user_id = users.id INNER JOIN projects "
            "ON time_entries.project_id=projects.id INNER JOIN enumerations "
            "ON enumerations.id=time_entries.activity_id INNER JOIN custom_values "
            "ON custom_values.customized_id = time_entries.id WHERE enumerations.name <> \'  Support (non-billable) \' "
            "AND custom_values.value NOT LIKE \'%%(internal)%%\' AND time_entries.project_id NOT IN %(list)s "
            "AND tmonth = %(month)s AND tyear = %(year)s GROUP BY users.lastname, users.firstname, "
            "custom_values.value, users.login, projects.name ORDER BY projects.name, users.login;" % {
                'month': request.GET['month'], 'year': request.GET['year'], 'list': required_list})

        day = calendar.monthrange(int(request.GET['year']), int(request.GET['month']))[1]
        unassigned = cur.fetchall()
        for record in unassigned:
            new_record = []
            new_record.append(record[5])  # Primary Comments
            new_record.append('')  # Customer Account Number (unknown)
            new_record.append(
                str(day) + '-' + calendar.month_abbr[int(request.GET['month'])].upper() + '-' + request.GET['year'][
                                                                                                2:])  # Transaction date
            new_record.append(cost_lib.get_cores_name(record[3]))  # Service Description
            new_record.append(record[0])  # Quantity (hours)
            new_record.append('Hour')  # Unit (Hours)
            new_record.append(cost_lib.get_cost(record[3]))  # Hourly Rate
            new_record.append(cost_lib.get_cores_name(record[3]))  # Service Category
            new_record.append('""')  # Secondary comments (always empty)
            new_record.append('""')  # Financially responsible PI (unknown)
            new_record.append('""')  # Purchaser's last name (unkown)
            new_record.append('""')  # Short contributing Center name (always empty)
            new_record.append('""')  # Resource Name (always empty)
            new_record.append('"' + record[4] + '"')  # Line item assistant (netID of the user)
            new_record.append('""')  # Line item comment (always empty)

            # write row!
            writer.writerow(new_record)

    return response


@login_required
@user_is_in_manager_group
def missing_hours(request):
    # connect to our database
    cur = connection.cursor()

    # gather a list of all projects
    cur.execute(
        "SELECT projects.id, projects.name FROM projects WHERE projects.id IN (SELECT customized_id "
        "FROM custom_values WHERE customized_type='Project' AND custom_field_id = 11 AND value = '1') "
        "ORDER BY projects.name;")
    dbprojects = cur.fetchall()

    # total list of projects
    projects = []

    # run through all projects, adding them to the list (as RedmineProject objects)
    for project in dbprojects:
        # get the fopal for this project
        cur.execute(
            "SELECT value FROM custom_values WHERE customized_id = %(project)s "
            "AND customized_type='Project' AND custom_field_id = 4" % {
                'project': project[0]})
        fopal = cur.fetchone()[0]

        # get the financially responsible PI (if any)
        cur.execute(
            'SELECT value FROM custom_values WHERE custom_field_id = 10 '
            'AND customized_id = %(project)s AND customized_type = \'Project\';' % {
                'project': project[0]})
        fpi = cur.fetchall()
        if len(fpi) >= 1:
            try:
                fpi = fpi[0][0]
                sfpi = fpi.split(' ')
                fpi = sfpi[1] + ', ' + sfpi[0]
            except:
                fpi = ''
        else:
            fpi = ''

        new_proj = RedmineProject(project_id=project[0], name=project[1], fopal=fopal, pi_name=fpi)
        projects.append(new_proj)

        # for each of these, grab any child projects
        projects += get_children(project[0])

    # prepare list for filtering
    required_list = '('
    for project_one in projects:
        project_id = project_one.id
        required_list += str(project_id) + ','
    required_list = required_list[:-1] + ')'

    cur.execute(
        'SELECT SUM(hours) FROM time_entries INNER JOIN users ON time_entries.user_id = users.id '
        'INNER JOIN projects ON time_entries.project_id=projects.id INNER JOIN enumerations '
        'ON enumerations.id=time_entries.activity_id INNER JOIN custom_values '
        'ON custom_values.customized_id = time_entries.id WHERE enumerations.name <> \'  Support (non-billable) \' '
        'AND custom_values.value NOT LIKE \'%%(external)%%\' AND time_entries.project_id NOT IN %(list)s '
        'AND tmonth = %(month)s AND tyear = %(year)s;' % {
            'month': request.GET['month'], 'year': request.GET['year'], 'list': required_list})
    missing_hours_count = cur.fetchone()[0]

    return HttpResponse(missing_hours_count)
