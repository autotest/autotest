============
 AFE Models
============

.. module:: autotest.frontend.afe.models

AFE stands for Autotest Front End. It's an application that provides access
to the core of Autotest definitions, such as Hosts, Tests, Jobs, etc.

For the classes that inherit from :class:`django.db.models.Model` some of the
attributes documented here are instances from one of the many
:mod:`django.db.models.fields` classes and will be mapped into a field on the
relational database.

:class:`AtomicGroup`
====================

.. autoclass:: AtomicGroup
    :members:


:class:`Job`
============

.. autoclass:: Job
    :members:


:class:`Label`
==============

.. autoclass:: Label
    :members:


:class:`Drone`
==============

.. autoclass:: Drone
    :members:


:class:`DroneSet`
=================

.. autoclass:: DroneSet
    :members:


:class:`User`
=============

.. autoclass:: User
    :members:


:class:`Host`
=============

.. autoclass:: Host
    :members:

:class:`HostAttribute`
======================

.. autoclass:: HostAttribute
    :members:

:class:`Test`
=============

.. autoclass:: Test
    :members:


:class:`TestParameter`
======================

.. autoclass:: TestParameter
    :members:

:class:`Profiler`
=================

.. autoclass:: Profiler
    :members:

:class:`AclGroup`
=================

.. autoclass:: AclGroup
    :members:

:class:`Kernel`
===============

.. autoclass:: Kernel
    :members:

:class:`ParameterizedJob`
=========================

.. autoclass:: ParameterizedJob
    :members:

:class:`ParameterizedJobProfiler`
=================================

.. autoclass:: ParameterizedJobProfiler
    :members:


:class:`ParameterizedJobProfilerParameter`
==========================================

.. autoclass:: ParameterizedJobProfilerParameter
    :members:

:class:`ParameterizedJobParameter`
==================================

.. autoclass:: ParameterizedJobParameter
    :members:

:class:`Job`
============

.. autoclass:: Job
    :members:


================
 AFE Exceptions
================

Besides persistence, Models also provide some logic. And as such, some custom
error conditions exist.

.. autoexception:: AclAccessViolation
