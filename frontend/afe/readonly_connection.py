from django import db as django_db
from django.conf import settings
from django.core import signals


class ReadOnlyConnection(object):

    """
    This class constructs a new connection to the DB using the read-only
    credentials from settings.  It reaches into some internals of
    django.db.connection which are undocumented as far as I know, but I believe
    it works across many, if not all, of the backends.
    """
    _the_instance = None

    # support singleton
    @classmethod
    def get_connection(cls):
        if cls._the_instance is None:
            cls._the_instance = ReadOnlyConnection()
        return cls._the_instance

    @classmethod
    def set_globally_disabled(cls, disabled):
        """
        When globally disabled, the ReadOnlyConnection will simply pass through
        to the global Django connection.
        """
        if disabled:
            cls._the_instance = DummyReadOnlyConnection()
        else:
            cls._the_instance = None

    def __init__(self):
        self._connection = None

    def _open_connection(self):
        if self._connection is not None:
            return
        self._save_django_state()
        self._connection = self._get_readonly_connection()
        self._restore_django_state()

    def _save_django_state(self):
        self._old_connection = django_db.connection.connection
        _default_db = settings.DATABASES['default']
        self._old_host = _default_db['HOST']
        self._old_username = _default_db['USER']
        self._old_password = _default_db['PASSWORD']

    def _restore_django_state(self):
        django_db.connection.connection = self._old_connection
        _default_db = settings.DATABASES['default']
        _default_db['HOST'] = self._old_host
        _default_db['USER'] = self._old_username
        _default_db['PASSWORD'] = self._old_password

    def _get_readonly_connection(self):
        _default_db = settings.DATABASES['default']
        _default_db['HOST'] = _default_db['READONLY_HOST']
        _default_db['USER'] = _default_db['READONLY_USER']
        _default_db['PASSWORD'] = _default_db['READONLY_PASSWORD']
        reload(django_db)
        # cursor() causes a new connection to be created
        cursor = django_db.connection.cursor()
        assert django_db.connection.connection is not None
        return django_db.connection.connection

    def set_django_connection(self):
        assert (django_db.connection.connection != self._connection or
                self._connection is None)
        self._open_connection()
        self._old_connection = django_db.connection.connection
        django_db.connection.connection = self._connection

    def unset_django_connection(self):
        assert self._connection is not None
        assert django_db.connection.connection == self._connection
        django_db.connection.connection = self._old_connection

    def cursor(self):
        self._open_connection()
        return self._connection.cursor()

    def close(self):
        if self._connection is not None:
            assert django_db.connection.connection != self._connection
            self._connection.close()
            self._connection = None


class DummyReadOnlyConnection(object):

    """
    A dummy version which passes queries straight to the global Django
    connection.
    """

    def __init__(self):
        self._is_set = False

    def set_django_connection(self):
        assert not self._is_set
        self._is_set = True

    def unset_django_connection(self):
        assert self._is_set
        self._is_set = False

    def cursor(self):
        return django_db.connection.cursor()

    def close(self):
        pass


# convenience
def connection():
    return ReadOnlyConnection.get_connection()


# close any open connection when request finishes
def _close_connection(**unused_kwargs):
    connection().close()
signals.request_finished.connect(_close_connection)
