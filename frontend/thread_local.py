import threading

# when using the models from a script, use this object to avoid null checks all
# over the place
class NullUser(object):
    def is_superuser(self):
        return True


_store = threading.local()
_store.user = NullUser()

def set_user(user):
    """\
    Sets the current request's logged-in user.  user should be a
    afe.models.User object.
    """
    _store.user = user


def get_user():
    'Get the currently logged-in user as a afe.models.User object.'
    return _store.user
