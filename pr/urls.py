"""pr URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url
from django.contrib import admin
from django.conf.urls import include

from time_management.planning import planning_home, get_all_dev_assignments, get_assignments, get_planning_projection, \
    developer_assignments, deactivate, activate, update_supervisor, remove_assignment, add_assignment

from time_management.home import home, get_entries_home, get_distribution, get_entries_home_page, get_all_distribution
from time_management.time_entries import entries_home, get_date_range, get_project_activities, update_entries, delete_entry
from time_management.calendar_view import calendar_home, update_entry_data, copy_entry
from time_management.distribution import distribution_home, get_entries
from time_management.report_generation import report_generator_home, generate_external_report, \
    generate_csr_report, generate_internal_report, missing_hours
from time_management.reports import weekly_report_form_url
from time_management.rates import rates_home, save_rate, save_start_date, save_end_date, save_rates, delete_rates, \
    add_rates, add_single_category
from time_management.auth import login_page, logout_request
from time_management.project_hours import project_hours_page, get_project_hours, get_users_for_project

# import cas.views
from django.conf import settings
from time_management.team_management import team_management, get_teams, get_team, save_manager, remove_team_member, \
    add_team_member, remove_team, create_team

urlpatterns = [
    url(r'^admin/', admin.site.urls),

    # ------------- For Everyone ----------------#
    # Home Page
    url(r'^$', home, name='home'),
    url(r'^get_entries$', get_entries_home, name="get_entries"),
    url(r'^get_all_entries$', get_entries_home_page, name="get_all_entries"),
    url(r'^get_distribution$', get_distribution, name="get_distribution"),
    url(r'^get_all_distribution$', get_all_distribution, name="get_all_distribution"),

    # Time Entries (row-by-row)
    url(r'^time_entries/$', entries_home, name="time_entries"),
    url(r'^get_dates$', get_date_range, name='get_dates'),
    url(r'^get_activities$', get_project_activities, name="get_activities"),
    url(r'^update_entries$', update_entries, name="update_entries"),
    url(r'^del_entry$', delete_entry, name='del_entry'),

    # Calendar View
    url(r'^calendar/$', calendar_home, name="calendar"),
    url(r'^update_entry_data$', update_entry_data, name="update_entry_data"),
    url(r'^copy_entry$', copy_entry, name="copy_entry_data"),

    # Time Distribution View
    url(r'^distribution/$', distribution_home, name="distribution"),
    url(r'^get_entities$', get_entries, name="get_entities"),


    # url(r'^skillsmatrix/', include('skillsmatrix.urls')),


    # ------------- Marcy's Report Generator for CORES -----------#
    url(r'^report_generator/$', report_generator_home, name='report_generator'),
    url(r'^generate_internal_report/$', generate_internal_report, name="report"),
    url(r'^generate_external_report/$', generate_external_report, name="report_external"),
    url(r'^generate_csr_report/$', generate_csr_report, name="report_external"),
    url(r'^missing_hours$', missing_hours, name="unassigned_hours"),


    # ------------- MANAGERS ONLY ----------------#

    # project hours
    url(r'^project_hours/$', project_hours_page, name='project_hours'),
    url(r'^project_hour_entries/$', get_project_hours, name='get_project_hours'),
    url(r'^get_users_for_project/$', get_users_for_project, name='get_project_users'),


    # team management
    url(r'^teams/$', team_management, name='team_management'),
    url(r'^get_teams/$', get_teams, name='get_teams'),
    url(r'^get_team$', get_team, name='get_team'),
    url(r'^save_manager', save_manager, name='save_manager'),
    url(r'^remove_team_member', remove_team_member, name='remove_team_member'),
    url(r'^add_team_member', add_team_member, name='add_team_member'),
    url(r'^remove_team', remove_team, name='remove_team'),
    url(r'^create_team', create_team, name='create_team'),

    # Project Planning
    url(r'^planning/$', planning_home, name='planning_home'),
    url(r'^get_all_dev_assignments$', get_all_dev_assignments, name='get_all_dev_assignments'),
    url(r'^get_assignments$', get_assignments, name='get_assignments'),
    url(r'^get_planning_projection$', get_planning_projection, name='getProjections'),
    url(r'^developer_assignments$', developer_assignments, name='dev_assignments'),
    url(r'^deactivate_developer$', deactivate, name='deactivate'),
    url(r'^activate_developer$', activate, name='activate'),
    url(r'^update_supervisor$', update_supervisor, name='update_supervisor'),
    url(r'^remove_project_distribution_entry$', remove_assignment, name='remove_assignment'),
    url(r'^add_developer$', add_assignment, name='add_developer'),

    # Adjustable Rates
    url(r'^rates/$', rates_home, name='rates_home'),
    url(r'^save_rate$', save_rate, name='save_rate'),
    url(r'^save_start_date$', save_start_date, name='save_start_date'),
    url(r'^save_end_date$', save_end_date, name='save_end_date'),
    url(r'^save_rates$', save_rates, name='save_rates'),
    url(r'^delete_rates$', delete_rates, name='delete_rates'),
    url(r'^add_rates$', add_rates, name='add_rates'),
    url(r'^add_single$', add_single_category, name='add_single'),

    # Weekly Report Generator (callable via the following URL):
    url(r'^weekly_report/$', weekly_report_form_url, name='weekly_report'),

    # Used if on production for CAS authentication
    # url(r'^login/$', cas.views.login, name='login'),
    # url(r'^logout/$', cas.views.logout, name='logout'),

    # OR you can use these login pages:
    #url(r'^accounts/login/$', cas.views.login, name='account_login'),
    #url(r'^accounts/logout/$', cas.views.logout, name='account_logout'),
    
    url(r'^login/$', login_page, name='login'),
    url(r'^logout/$', logout_request, name='logout'),



]
