======================================
 Dependency Checking and Installation
======================================

.. module:: autotest.client.shared.deps

The Autotest client library has functionality that lets test writers explicitly
check for dependencies and even try to fulfill them.

Checking for a given command (executable file)
==============================================

A check in this module context means that a depency is required and an error
should be thrown if it's not satified.

The most basic dependency for a test is to be able to run a external command,
or how it's commonly called, an executable.

Because different systems have different filesystem layouts, it's usually
useful to lookup the command in the currently set PATH. This is exactly
what the :func:`executable` does.

Its usage is quite straighforward::

    >>> from autotest.client.shared import deps
    >>> deps.executable('foo')

If your system has an executable named foo somewhere in the PATH, the complete
path of that file will be returned. If your system does not have the needed
executable, an :exc:`DependencyNotSatisfied` exception will be raised.

Checking for a given package
----------------------------

If your test has a requirement on a package, which may hold not only an
executable but data files that will be used directly or indirectly, you can
check for a package instead.

Here is a sample usage::

    >>> from autotest.client.shared import deps
    >>> deps.package('foo')

This will also raise :exc:`DependencyNotSatisfied` if the package foo is
not installed.


API Reference
=============

:func:`executable`
------------------

.. autofunction:: executable


:func:`packge`
--------------

.. autofunction:: package


Exceptions
----------

.. autoexception:: DependencyNotSatisfied
