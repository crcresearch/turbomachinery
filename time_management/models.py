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
    manager = models.ForeignKey(RedmineUser, related_name='redmineuser_manager', on_delete=models.CASCADE)

    def __unicode__(self):
        return str(self.manager)


class TeamMember(models.Model):
    team = models.ForeignKey(Team, related_name='team_teammember', null=True, blank=True, on_delete=models.CASCADE)
    member = models.ForeignKey(RedmineUser, related_name='redmineuser_teammember', on_delete=models.CASCADE)

    def __unicode__(self):
        return str(self.team) + ': ' + str(self.member)