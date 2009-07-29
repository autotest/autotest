# Copyright 2009 Google Inc. Released under the GPL v2

# This file contains the classes used for the known kernel versions persistent
# storage

import cPickle

class item(object):
    """Wrap a file item stored in a database."""
    def __init__(self, name, size, timestamp):
        assert type(size) == int
        assert type(timestamp) == int

        self.name = name
        self.size = size
        self.timestamp = timestamp


    def __repr__(self):
        return ("database.item('%s', %d, %d)" %
                (self.name, self.size, self.timestamp))


    def __eq__(self, other):
        if not isinstance(other, item):
            return NotImplemented

        return (self.name == other.name and self.size == other.size and
                self.timestamp == other.timestamp)


    def __ne__(self, other):
        return not self.__eq__(other)


class database(object):
    """
    This is an Abstract Base Class for the file items database, not strictly
    needed in Python because of the dynamic nature of the language but useful
    to document the expected common API of the implementations.
    """

    def get_dictionary(self):
        """
        Should be implemented to open and read the persistent contents of
        the database and return it as a key->value dictionary.
        """
        raise NotImplemented('get_dictionary not implemented')


    def merge_dictionary(self, values):
        """
        Should be implemented to merge the "values" dictionary into the
        database persistent contents (ie to update existent entries and to add
        those that do not exist).
        """
        raise NotImplemented('merge_dictionary not implemented')


class dict_database(database):
    """
    A simple key->value database that uses standard python pickle dump of
    a dictionary object for persistent storage.
    """
    def __init__(self, path):
        self.path = path


    def get_dictionary(self, _open_func=open):
        """
        Return the key/value pairs as a standard dictionary.
        """
        try:
            fd = _open_func(self.path, 'rb')
        except IOError:
            # no db file, considering as if empty dictionary
            res = {}
        else:
            res = cPickle.load(fd)

        return res


    def merge_dictionary(self, values, _open_func=open):
        """
        Merge the contents of "values" with the current contents of the
        database.
        """
        if not values:
            return

        contents = self.get_dictionary()
        contents.update(values)
        # FIXME implement some kind of protection against full disk problem
        cPickle.dump(contents, _open_func(self.path, 'wb'),
                     protocol=cPickle.HIGHEST_PROTOCOL)
