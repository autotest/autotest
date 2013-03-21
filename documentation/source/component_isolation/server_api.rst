============
 Server API
============

.. module:: autotest.tko.installed_software_parser

When programming code on the Autotest server side, it could be necessary to
have access to the component isolation functionality.

For that there's an API that gives you access to that data in a easier way than
manipulating the database object models themselves.


Creating :class:`SoftwareKind`
==============================

If you want to create a new Software Kind you can use:

.. autofunction:: create_kind

Creating :class:`SoftwareArch`
==============================

If you want to create a new Software Arch you can use:

.. autofunction:: create_arch

Creating :class:`SoftwareComponent`
===================================

If you want to create a new Software Component you can use:

.. autofunction:: create_software_component

Also, there are utility methods to create a :class:`SoftwareComponent` from a
textual representation:

.. autofunction:: create_software_component_from_line

And also from a file containing many lines:

.. autofunction:: parse_file
