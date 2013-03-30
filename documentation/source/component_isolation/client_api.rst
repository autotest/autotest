============
 Client API
============

The Component Isolation feature includes some explicit and some implicit APIs
that allow tests to record the test environment they are using during a test.

Explicitly recording installed software
=======================================

.. module:: autotest.client.shared.test

A test can explicitly record that a given piece of software that may influence
the test outcome was installed by means of calling a newly added API on the
:class:`base_test` object.

.. automethod:: base_test.record_software_install

