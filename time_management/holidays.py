import datetime
from dateutil.relativedelta import relativedelta
import calendar
import psycopg2

AVG_HOUR_BILL = 131
AVG_MAN_BILL = 80


def get_winter_break(month, year):
    """
    Depending on what day Christmas falls on, we adjust how many days we get off.
    This also depends on if the passed in month is 1 or 12 (January or December).

    If Christmas Falls On:		Xmas Celebration:		New Years:
    (6) Saturday			Dec 24-Dec 30			Dec 31 - Jan 1
    (7) Sunday			Dec 23-Dec 30			Dec 31 - Jan 2
    (1) Monday			Dec 22-Dec 30			Dec 31 - Jan 1
    (2) Tuesday			Dec 24-Dec 30			Dec 31 - Jan 1
    (3) Wednesday			Dec 23-Dec 30			Dec 31 - Jan 1
    (4) Thursday			Dec 24-Dec 30			Dec 31 - Jan 2
    (5) Friday			Dec 24-Dec 30			Dec 31 - Jan 1
    """
    # create the date we're looking for (Christmas of this year)
    if month == 1:
        year -= 1

    christmas = datetime.date(year, 12, 25)

    # what day of the week is this?
    if christmas.isoweekday() == 7:
        start_date = datetime.date(year, 12, 23)
        end_date = datetime.date(year + 1, 1, 2)
    if christmas.isoweekday() == 1:
        start_date = datetime.date(year, 12, 22)
        end_date = datetime.date(year + 1, 1, 1)
    if christmas.isoweekday() == 2:
        start_date = datetime.date(year, 12, 24)
        end_date = datetime.date(year + 1, 1, 1)
    if christmas.isoweekday() == 3:
        start_date = datetime.date(year, 12, 23)
        end_date = datetime.date(year + 1, 1, 1)
    if christmas.isoweekday() == 4:
        start_date = datetime.date(year, 12, 24)
        end_date = datetime.date(year + 1, 1, 2)
    if christmas.isoweekday() == 5:
        start_date = datetime.date(year, 12, 24)
        end_date = datetime.date(year + 1, 1, 1)
    if christmas.isoweekday() == 6:
        start_date = datetime.date(year, 12, 24)
        end_date = datetime.date(year + 1, 1, 1)

    # now create a list of days we have "off" from start_date to end_date
    days_off = []
    current_date = start_date
    # loop through all dates between our start and end vacation days
    while current_date <= end_date:
        # only add it if it is a weekday (of course we don't work weekends!)
        if current_date.isoweekday() != 7 and current_date.isoweekday() != 6:
            holiday = {}
            holiday['date'] = current_date
            if current_date == end_date or current_date == (end_date - datetime.timedelta(days=1)):
                holiday['name'] = 'New Years Celebration'
            else:
                holiday['name'] = 'Christmas Break'
            days_off.append(holiday)
        # go to the next date!
        current_date = current_date + datetime.timedelta(days=1)

    # return our list of dates for our Winter Break! Merry Christmas and Happy New Year!! :D
    return days_off


def get_good_friday(year):
    """
    Returns the date of Good Friday for the year passed in.
    (NOTE: Algorithm for determining Easter taken from "Butcher's Algorithm" for determining
    Easter for the Western Church.
    Works on any date 1583 and onward.
    Reference: http://code.activestate.com/recipes/576517-calculate-easter-western-given-a-year/).
    """
    a = year % 19
    b = year // 100
    c = year % 100
    d = (19 * a + b - b // 4 - ((b - (b + 8) // 25 + 1) // 3) + 15) % 30
    e = (32 + 2 * (b % 4) + 2 * (c // 4) - d - (c % 4)) % 7
    f = d + e - 7 * ((a + 11 * d + 22 * e) // 451) + 114
    month = f // 31
    day = f % 31 + 1

    # Just for records:
    # easter = date(year, month, day)

    # now that we have Easter, Good Friday is just 2 days prior!
    holiday = {}
    holiday['date'] = datetime.date(year, month, day) - datetime.timedelta(days=2)
    holiday['name'] = 'Good Friday'
    return holiday


def get_memorial_day(year):
    """
    Returns the date of Memorial Day (last Monday in May).
    """
    # first get the last day of the month in May
    day = datetime.date(year, 6, 1) - datetime.timedelta(days=1)

    # keep decrementing our "day" until we hit a Monday
    while day.isoweekday() != 1:
        day = day - datetime.timedelta(days=1)

    holiday = {}
    holiday['date'] = day
    holiday['name'] = 'Memorial Day'

    # return our day!
    return holiday


def get_independence_day(year):
    """
    Returns the day for celebrating Indedependence Day.
    If July 4th falls on Saturday, the previous Friday is off.
    If July 4th falls on Sunday, the next Monday is off.
    """
    independence_day = datetime.date(year, 7, 4)

    # if July 4th is a Saturday...
    if independence_day.isoweekday() == 6:
        # we celebrate the previous day (Friday)
        independence_day = datetime.date(year, 7, 3)
    # if July 4th is a Sunday...
    if independence_day.isoweekday() == 7:
        # we celebrate the next day (Monday)
        independence_day = datetime.date(year, 7, 5)

    holiday = {}
    holiday['date'] = independence_day
    holiday['name'] = 'Independence Day'

    return holiday


def get_labor_day(year):
    """
    Returns the day for Labor Day of the given year. (First Monday in September)
    """
    laborday = datetime.date(year, 9, 1)

    # until we reach a monday, keep adding 1 day
    while laborday.isoweekday() != 1:
        laborday = laborday + datetime.timedelta(days=1)

    holiday = {}
    holiday['date'] = laborday
    holiday['name'] = 'Labor Day'

    return holiday


def get_thanksgiving_break(year):
    """
    Returns the date of Thanksgiving and the following Friday (we always get those two days off).
    Thanksgiving is always the 4th Thursday of November.
    """
    # get the first day of November
    day = datetime.date(year, 11, 1)

    # have we reached a thursday yet?
    thursday = False

    # until we reach the 4th Thursday...
    while not thursday:
        # is our current date a thursday?
        if day.isoweekday() == 4:
            thursday = True
        else:
            day = day + datetime.timedelta(days=1)

    # now that we're out of the loop, our current day is the first Thursday of the month.
    # So all we need to do is add 3 weeks to this day.
    thanksgiving = day + datetime.timedelta(weeks=3)

    # now return thanksgiving, plus the following day! Gobble-gobble!
    holiday1 = {}
    holiday2 = {}
    holiday1['date'] = thanksgiving
    holiday2['date'] = (thanksgiving + datetime.timedelta(days=1))
    holiday1['name'] = 'Thanksgiving Break'
    holiday2['name'] = 'Thanksgiving Break'
    return [holiday1, holiday2]


def get_closings(year):
    """
    Returns a list of dates within the year passed in of
    University Closings (non-holidays, such as Snow days)
    This list is collected from the "closings" table
    within the database.
    """
    # connect to the redmine database
    connection = psycopg2.connect(database="redmine", user="redmine")
    cursor = connection.cursor()

    # get all of the dates within this year
    cursor.execute("SELECT date, reason FROM closings WHERE EXTRACT(YEAR FROM date) = '%s';" % year)
    dates = cursor.fetchall()

    date_list = []
    for day in dates:
        holiday = {}
        holiday['date'] = day[0]
        holiday['name'] = day[1]
        date_list.append(holiday)

    return date_list


def get_holidays(year):
    """
    Returns a list of dates which are paid holidays.
    """
    paid_holidays = []
    paid_holidays += get_winter_break(1, year) + get_winter_break(12, year)
    paid_holidays.append(get_good_friday(year))
    paid_holidays.append(get_memorial_day(year))
    paid_holidays.append(get_independence_day(year))
    paid_holidays.append(get_labor_day(year))
    paid_holidays += get_thanksgiving_break(year)

    return paid_holidays


def get_average_day_hours(current_month, current_year, monthly_expected):
    avg_year = monthly_expected * 12  # how many hours (average for the year)

    # how many working days are there this fiscal year?
    # we need to find last July 1
    july = datetime.date(current_year, 7, 1)
    if current_month < 7:
        july = datetime.date(current_year - 1, 7, 1)

    holidays = get_holidays(current_year)
    if current_year < 7:
        holidays += (get_holidays(current_year - 1))
    else:
        holidays += (get_holidays(current_year + 1))

    current_date = july
    end_date = datetime.date(july.year + 1, 7, 1)
    working_days = 0
    while current_date < end_date:
        working_days += get_working_days(current_date.month, current_date.year)
        current_date = current_date + relativedelta(months=1)

    print(working_days)

    avg_hours_per_day = float(avg_year) / float(working_days)
    return avg_hours_per_day


def get_working_days(month, year):
    holidays = get_holidays(year)
    current_date = datetime.date(year, month, 1)
    end_date = datetime.date(year, month, calendar.monthrange(year, month)[1])
    working_days = 0

    while current_date <= end_date:
        # is this a weekend?
        if current_date.weekday() < 5:
            is_holiday = False
            for holiday in holidays:
                if current_date == holiday['date']:
                    is_holiday = True
            if not is_holiday:
                working_days += 1
        current_date = current_date + datetime.timedelta(days=1)
    return working_days


def get_average_hours_for_month(month, year):
    average_hours_per_day = get_average_day_hours(month, year, AVG_HOUR_BILL)
    working_days_count = float(get_working_days(month, year))

    return working_days_count * average_hours_per_day


def get_average_hours_for_month_managers(month, year):
    average_hours_per_day = get_average_day_hours(month, year, AVG_MAN_BILL)
    working_days_count = float(get_working_days(month, year))

    return working_days_count * average_hours_per_day
