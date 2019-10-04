from django.shortcuts import HttpResponse, render
from django.db import connection
import json
from django.contrib.auth.decorators import user_passes_test

from django.contrib.auth.decorators import login_required
from time_management.models import TeamMember, RedmineUser, Team
from time_management.decorators import user_is_in_manager_group

@login_required
@user_passes_test(lambda u: u.is_staff)
def team_management(request):
    return render(request, 'teams.html', {'team_list': get_team_list(),
                                          'users': RedmineUser.objects.all().order_by('lastname', 'firstname')})


def get_team_list():
    # get a list of team managers
    teams = Team.objects.all()
    # managers = TeamMember.objects.values('manager').distinct()

    # for each manager, get a list of team members
    team_list = []
    for team in teams:
        member_ids = []
        team_manager = team.manager
        members = TeamMember.objects.filter(team=team)

        member_list = []
        for member in members:
            redmine_user = member.member

            member_obj = {
                'name': str(redmine_user),
                'id': member.id
            }
            if member.member.id in member_ids:
                # then we have a duplicate, so remove it
                member.delete()
            else:
                member_ids.append(member.member.id)
                member_list.append(member_obj)

        team_list.append({
            'manager': {
                'name': str(team_manager),
                'id': team_manager.id
            },
            'members': member_list,
            'id': team.id
        })

    return team_list


@login_required
@user_passes_test(lambda u: u.is_staff)
def get_teams(request):
    return HttpResponse(json.dumps(get_team_list()))


def get_specific_team(team_id):
    team = Team.objects.get(id=team_id)
    team_manager = team.manager
    members = TeamMember.objects.filter(team=team)

    member_list = []
    member_ids = []
    for member in members:
        redmine_user = member.member
        member_obj = {
            'name': str(redmine_user),
            'id': member.id
        }
        if member.member.id in member_ids:
            # then we have a duplicate, so remove it
            member.delete()
        else:
            member_ids.append(member.member.id)
            member_list.append(member_obj)

    return json.dumps({
        'manager': {
            'name': str(team_manager),
            'id': team_manager.id
        },
        'members': member_list,
        'id': team_id
    })

@login_required
@user_passes_test(lambda u: u.is_staff)
def get_team(request):
    return HttpResponse(get_specific_team(team_id=request.GET['team_id']))


@login_required
@user_passes_test(lambda u: u.is_staff)
def save_manager(request):
    team = Team.objects.get(id=request.GET['team_id'])
    new_manager = RedmineUser.objects.get(id=request.GET['manager'])
    team.manager = new_manager
    team.save()

    return HttpResponse(get_specific_team(team_id=request.GET['team_id']))


@login_required
@user_passes_test(lambda u: u.is_staff)
def remove_team_member(request):
    team_member = TeamMember.objects.get(id=request.GET['id'])
    team_id = team_member.team.id
    team_member.delete()

    return HttpResponse(get_specific_team(team_id=team_id))


@login_required
@user_passes_test(lambda u: u.is_staff)
def add_team_member(request):
    team = Team.objects.get(id=request.GET['team_id'])
    redmine_user = RedmineUser.objects.get(id=request.GET['member'])

    team_member, created = TeamMember.objects.get_or_create(
        team=team,
        member=redmine_user
    )
    team_member.save()

    return HttpResponse(get_specific_team(team_id=team.id))


@login_required
@user_passes_test(lambda u: u.is_staff)
def remove_team(request):
    team = Team.objects.get(id=request.GET['team_id'])
    team.delete()

    return HttpResponse(request.GET['team_id'])


@login_required
@user_passes_test(lambda u: u.is_staff)
def create_team(request):
    manager_obj = RedmineUser.objects.get(id=request.GET['manager'])
    team = Team(
        manager=manager_obj
    )
    team.save()

    return HttpResponse(get_specific_team(team_id=team.id))
