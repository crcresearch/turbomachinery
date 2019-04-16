import datetime

from holidays import get_holidays, get_working_days
from time_management.models import Team, RedmineUser

def get_monthly_expected(month=datetime.datetime.now().month, year=datetime.datetime.now().year):
    # get the first and last day of the month
    last = datetime.date(year, (month + 1), 1) - datetime.timedelta(days=1)

    # get our holidays
    holiday_list = get_holidays(year)

    # setup a count for all weekdays
    # (Monday = [0], Tuesday = [1], etc...)
    weekdays = [0, 0, 0, 0, 0, 0, 0]

    # loop through from first to last day
    day = 1
    while day <= last.day:
        # get the new date
        next_day = datetime.date(year, month, day)
        # add one day to this week if it's not a paid holiday
        if next_day not in holiday_list:
            weekdays[next_day.weekday()] += 1
        day += 1

    # add up how many weekdays we have (Monday-Friday: [0]->[4])
    total = weekdays[0] + weekdays[1] + weekdays[2] + weekdays[3] + weekdays[4]

    return total * 8


def date_working_hours(day):
    if day.weekday() >= 5:
        return 0

    if day in get_holidays(day.year):
        return 0

    return 8


def manager_date_working_hours(day):
    if day.weekday() >= 5:
        return 0

    if day in get_holidays(day.year):
        return 0

    working_days = get_working_days(day.month, day.year)

    return float(30) / float(working_days)


def get_user_list(username, as_json=False, include_manager=True):
    """
    Given a user ID, look up any teams this user is a manager for.  If they are, return a list of user IDs that are
    part of this team (including the user themselves).  If not, return only the user.
    :param username:
    :return: List of user IDs they are a manager for, OR just their own.
    """

    # get their Redmine user id
    user = RedmineUser.objects.get(login=username)
    user_id = user.id
    user_ids = []

    if include_manager:
        user_ids.append(user_id)

    # grab a list teams they are a manager for (if any)
    teams = Team.objects.filter(manager__id=user_id)

    for team in teams:
        # grab a list of team members
        for member in team.team_teammember.all():
            if member.member.id not in user_ids:
                user_ids.append(member.member.id)

    if len(user_ids) == 1:
        if as_json:
            return [user_id]
        return '('+str(user_id)+')'

    if as_json:
        return user_ids
    return str(tuple(user_ids))


def get_all_users():
    """
    Returns a tuple of all user ids.
    :return:
    """
    users = RedmineUser.objects.all()

    user_list = []
    for user in users:
        user_list.append(user.id)

    return user_list
