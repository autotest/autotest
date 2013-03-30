============================
 Component Isolation Models
============================

.. module:: autotest.frontend.afe.models

Component Isolation is not exactly an application, but a set of features that
touch many parts of Autotest.

On the RPC server, a set of models are used to store and fetch information.
Because of the trend to unite the model files, and also becuase the AFE
application model module is the largest of the two, the Component Isolation
models are stored on the :mod:`autotest.frontend.afe.models` module.

:class:`SoftwareComponentKind`
==============================

.. autoclass:: SoftwareComponentKind
    :members:


:class:`SoftwareComponentArch`
==============================

.. autoclass:: SoftwareComponentArch
    :members:


:class:`SoftwareComponent`
==========================

.. autoclass:: SoftwareComponent
    :members:


:class:`LinuxDistro`
====================

.. autoclass:: LinuxDistro
    :members:


:class:`TestEnvironment`
========================

.. autoclass:: TestEnvironment
    :members:
