"""
This module contains backported functions that are not present on Python 2.4
but are standard in more recent versions.
"""

import re


# pylint: disable=I0011,W0622
# noinspection PyShadowingBuiltins
def next(*args):
    """
    Retrieve the next item from the iterator by calling its next() method.
    If default is given, it is returned if the iterator is exhausted,
    otherwise StopIteration is raised.
    New in version 2.6.

    :param iterator: the iterator
    :type iterator: iterator
    :param default: the value to return if the iterator raises StopIteration
    :type default: object
    :return: The object returned by iterator.next()
    :rtype: object
    """
    if len(args) == 2:
        try:
            return args[0].next()
        except StopIteration:
            return args[1]
    elif len(args) > 2:
        raise TypeError("next expected at most 2 arguments, %s" % len(args))
    else:
        return args[0].next()

# pylint: disable=W0622
# noinspection PyShadowingBuiltins


def any(iterable):
    """
    From http://stackoverflow.com/questions/3785433/python-backports-for-some-methods
    :codeauthor: Tim Pietzcker  http://stackoverflow.com/users/20670/tim-pietzcker
    licensed under cc-wiki with attribution required
    """
    for element in iterable:
        if element:
            return True
    return False


# pylint: disable=W0622
# noinspection PyShadowingBuiltins
def all(iterable):
    """
    From http://stackoverflow.com/questions/3785433/python-backports-for-some-methods
    :codeauthor: Tim Pietzcker  http://stackoverflow.com/users/20670/tim-pietzcker
    licensed under cc-wiki with attribution required
    """
    for element in iterable:
        if not element:
            return False
    return True


# Adapted from http://code.activestate.com/recipes/576847/
# :codeauthor: Vishal Sapre
# :license: MIT
BIN_HEX_DICT = {
    '0': '0000', '1': '0001', '2': '0010', '3': '0011', '4': '0100',
    '5': '0101', '6': '0110', '7': '0111', '8': '1000', '9': '1001',
    'a': '1010', 'b': '1011', 'c': '1100', 'd': '1101', 'e': '1110',
    'f': '1111', 'L': ''}

# match left leading zeroes, but don't match a single 0 for the case of
# bin(0) == '0b0'
BIN_ZSTRIP = re.compile(r'^0*(?=[01])')


# pylint: disable=W0622
# noinspection PyShadowingBuiltins
def bin(number):
    """
    Adapted from http://code.activestate.com/recipes/576847/
    :codeauthor: Vishal Sapre
    :license: MIT

    A foolishly simple look-up method of getting binary string from an integer
    This happens to be faster than all other ways!!!
    """
    # =========================================================
    # create hex of int, remove '0x'. now for each hex char,
    # look up binary string, append in list and join at the end.
    # =========================================================
    # replace leading left zeroes with '0b'
    tmp = [BIN_HEX_DICT[hstr] for hstr in hex(number)[2:]]
    return BIN_ZSTRIP.sub('0b', ''.join(tmp))
