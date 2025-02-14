from django.db import models


class RedmineUser(models.Model):
    login = models.CharField(max_length=100)
    hashed_password = models.CharField(max_length=40)
    firstname = models.CharField(max_length=30)
    lastname = models.CharField(max_length=255)
    admin = models.BooleanField()
    status = models.IntegerField()
    last_login_on = models.DateTimeField(blank=True, null=True)
    language = models.CharField(max_length=5, blank=True, null=True)
    auth_source_id = models.IntegerField(blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)
    type = models.CharField(max_length=1000, blank=True, null=True)
    identity_url = models.CharField(max_length=1000, blank=True, null=True)
    mail_notification = models.CharField(max_length=1000)
    salt = models.CharField(max_length=64, blank=True, null=True)
    must_change_passwd = models.BooleanField()
    passwd_changed_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'users'

    def __unicode__(self):
        return self.firstname + ' ' + self.lastname


class Team(models.Model):
    manager = models.ForeignKey(RedmineUser, related_name='redmineuser_manager')

    def __unicode__(self):
        return str(self.manager)


class TeamMember(models.Model):
    team = models.ForeignKey(Team, related_name='team_teammember', null=True, blank=True)
    member = models.ForeignKey(RedmineUser, related_name='redmineuser_teammember')

    def __unicode__(self):
        return str(self.team) + ': ' + str(self.member)


class TimeEntry(models.Model):
    user = models.ForeignKey('RedmineUser', models.DO_NOTHING)
    project = models.ForeignKey('Project', models.DO_NOTHING)
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    comments = models.TextField(blank=True, null=True)
    activity = models.ForeignKey('Enumeration', models.DO_NOTHING)
    spent_on = models.DateField()
    created_on = models.DateTimeField()
    updated_on = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'time_entries'


class Project(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    identifier = models.CharField(unique=True, max_length=255)
    status = models.IntegerField()
    
    class Meta:
        managed = False
        db_table = 'projects'


class Enumeration(models.Model):
    name = models.CharField(max_length=30)
    position = models.IntegerField(blank=True, null=True)
    is_default = models.BooleanField()
    type = models.CharField(max_length=255)
    active = models.BooleanField()
    project_id = models.IntegerField(blank=True, null=True)
    parent_id = models.IntegerField(blank=True, null=True)
    position_name = models.CharField(max_length=30, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'enumerations'