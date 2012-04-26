"""\
Generic enumeration support.
"""

__author__ = 'showard@google.com (Steve Howard)'

class Enum(object):
    """\
    Utility class to implement Enum-like functionality.

    >>> e = Enum('String one', 'String two')
    >>> e.STRING_ONE
    0
    >>> e.STRING_TWO
    1
    >>> e.choices()
    [(0, 'String one'), (1, 'String two')]
    >>> e.get_value('String one')
    0
    >>> e.get_string(0)
    'String one'

    >>> e = Enum('Hello', 'Goodbye', string_values=True)
    >>> e.HELLO, e.GOODBYE
    ('Hello', 'Goodbye')

    >>> e = Enum('One', 'Two', start_value=1)
    >>> e.ONE
    1
    >>> e.TWO
    2
    """
    def __init__(self, *names, **kwargs):
        self.string_values = kwargs.get('string_values')
        start_value = kwargs.get('start_value', 0)
        self.names = names
        self.values = []
        for i, name in enumerate(names):
            if self.string_values:
                value = name
            else:
                value = i + start_value
            self.values.append(value)
            setattr(self, self.get_attr_name(name), value)


    @staticmethod
    def get_attr_name(string):
        return string.upper().replace(' ', '_')


    def choices(self):
        'Return choice list suitable for Django model choices.'
        return zip(self.values, self.names)


    def get_value(self, name):
        """\
        Convert a string name to it's corresponding value.  If a value
        is passed in, it is returned.
        """
        if isinstance(name, int) and not self.string_values:
            # name is already a value
            return name
        return getattr(self, self.get_attr_name(name))


    def get_string(self, value):
        ' Given a value, get the string name for it.'
        if value not in self.values:
            raise ValueError('Value %s not in this enum' % value)
        index = self.values.index(value)
        return self.names[index]
