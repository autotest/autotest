Linux distribution detection
============================
.. module:: autotest.client.shared.distro

Autotest has a facility that lets tests determine quite precisely the distribution they're running on.

This is done through the implementation and registration of probe classes.

Those probe classes can check for given characteristics of the running operating system, such as the existence of a release file,
its contents or even the existence of a binary that is exclusive to a distribution (such as package managers).

Quickly detecting the Linux distribution
========================================
The :mod:`autotest.client.shared.distro` module provides many APIs, but the simplest one to use is the :func:`detect`.

Its usage is quite straighforward::

 from autotest.client.shared import distro
 detected_distro = distro.detect()

The returned distro can be the result of a probe validating the distribution detection, or the not so useful
:data:`UNKNOWN_DISTRO`.

To access the relevant data on a :class:`LinuxDistro`, simply use the attributes:

* :attr:`name <LinuxDistro.name>`
* :attr:`version <LinuxDistro.version>`
* :attr:`release <LinuxDistro.release>`
* :attr:`arch <LinuxDistro.arch>`

Example::

 >>> detected_distro = distro.detect()
 >>> print detected_distro.name
 redhat


The unknown Linux distribution
==============================
When the detection mechanism can't precily detect the Linux distribution, it will still return a :class:`LinuxDistro` instance,
but a special one that contains special values for its name, version, etc.

.. autodata:: UNKNOWN_DISTRO

Writing a Linux distribution probe
==================================
The easiest way to write a probe for your target Linux distribution is to make use of the features of the :class:`Probe` class.

Even if you do plan to use the features documented here, keep in mind that all probes should inherit from :class:`Probe`
and provide a basic interface.

Checking the distrution name only
---------------------------------
The most trivial probe is one that checks the existence of a file and returns the distribution name::

 class RedHatProbe(Probe):
  CHECK_FILE = '/etc/redhat-release'
  CHECK_FILE_DISTRO_NAME = 'redhat'

To make use of a probe, it's necessary to register it::

 from autotest.client.shared import distro
 distro.register_probe(RedHatProbe)

And that's it. This is a valid example, but will give you nothing but the distro name.

You should usually aim for more information, such as the version numbers.

Checking the distribution name and version numbers
--------------------------------------------------
If you want to also detect the distro version numbers (and you should), then it's possible to use the
:attr:`Probe.CHECK_VERSION_REGEX` feature of the :class:`Probe` class.

.. autoattribute:: Probe.CHECK_VERSION_REGEX

If your regex has two or more groups, that is, it will look for and save references to two or more string, it will consider
the second group to be the :attr:`LinuxDistro.release` number.

Probe Scores
------------
To increase the accuracy of the probe results, it's possible to register a score for a probe. If a probe wants to, it can
register a score for itself.

Probes that return a score will be given priority over probes that don't.

The score should be based on the number of checks that ran during the probe to account for its accuracy.

Probes should not be given a higher score because their checks look more precise than everyone else's.

Registering your own probes
---------------------------
Not only the probes that ship with Autotest can be used, but your custom probe classes can be added to the detection system.

To do that simply call the function :func:`register_probe`:

.. autofunction:: register_probe

Now, remember that for things to happen smootlhy your registered probe must be a subclass of :class:`Probe`.


API Reference
=============

:class:`LinuxDistro`
--------------------

.. autoclass:: LinuxDistro
    :members:

:class:`Probe`
--------------

.. autoclass:: Probe
    :members:

:func:`register_probe`
----------------------

.. autofunction:: register_probe

:func:`detect`
--------------

.. autofunction:: detect
