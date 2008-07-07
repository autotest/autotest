import threading

_store = threading.local()
_store.user = None

def set_user(user):
    """\
    Sets the current request's logged-in user.  user should be a
    afe.models.User object.
    """
    _store.user = user


def get_user():
    'Get the currently logged-in user as a afe.models.User object.'
    return _store.user
