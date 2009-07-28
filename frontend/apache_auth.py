from django.contrib.auth.models import User, Group, check_password
from django.contrib.auth import backends
from django.contrib import auth
from django import http

from autotest_lib.frontend import thread_local
from autotest_lib.frontend.afe import models, management

DEBUG_USER = 'debug_user'

class SimpleAuthBackend(backends.ModelBackend):
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


class GetApacheUserMiddleware(object):
    """
    Middleware for use when Apache is doing authentication.  Looks for
    REMOTE_USER in headers and passed the username found to
    thread_local.set_user().  If no such header is found, looks for
    HTTP_AUTHORIZATION header with username (this allows CLI to authenticate).
    If neither of those are found, DEBUG_USER is used.
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
        thread_local.set_user(user)


class ApacheAuthMiddleware(GetApacheUserMiddleware):
    """
    Like GetApacheUserMiddleware, but also logs the user into Django's auth
    system, and replaces the username in thread_local with the actual User model
    object.
    """


    def process_request(self, request):
        super(ApacheAuthMiddleware, self).process_request(request)
        username = thread_local.get_user()
        thread_local.set_user(None)
        user_object = auth.authenticate(username=username,
                                        password='')
        auth.login(request, user_object)
        thread_local.set_user(models.User.objects.get(login=username))
