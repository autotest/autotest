from django.contrib.auth.models import User, Group, check_password
from django.contrib import auth
from django import http

from frontend import thread_local
from frontend.afe import models, management

DEBUG_USER = 'debug_user'

class SimpleAuthBackend:
    """
    Automatically allows any login.  This backend is for use when Apache is
    doing the real authentication.  Also ensures logged-in user exists in
    frontend.afe.models.User database.
    """
    def authenticate(self, username=None, password=None):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # password is meaningless
            user = User(username=username,
                        password='apache authentication')
            user.is_staff = True
            user.save() # need to save before adding groups
            user.groups.add(Group.objects.get(
                name=management.BASIC_ADMIN))

        SimpleAuthBackend.check_afe_user(username)
        return user


    @staticmethod
    def check_afe_user(username):
        user, created = models.User.objects.get_or_create(login=username)
        if created:
            user.save()

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


class ApacheAuthMiddleware(object):
    """
    Middleware for use when Apache is doing authentication.  Looks for
    REQUEST_USER in requests and logs that user in.  If no such header is
    found, looks for HTTP_AUTHORIZATION header with username to login (this
    allows CLI to authenticate).
    """

    def process_request(self, request):
        # look for a username from Apache
        user = request.META.get('REMOTE_USER')
        if user is None:
            # look for a user in headers.  This is insecure but
            # it's our temporarily solution for CLI auth.
            user = request.META.get('HTTP_AUTHORIZATION')
        if user is None:
            # no user info - assume we're in development mode
            user = DEBUG_USER
        user_object = auth.authenticate(username=user,
                                        password='')
        auth.login(request, user_object)
        thread_local.set_user(models.User.objects.get(login=user))
        return None
