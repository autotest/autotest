============
 RPC Server
============

The Autotest RPC Server, also known as the frontend, is a Django based
application that provides:

* The Database Objects (defined by Django :mod:`Models <django.db.models>`)
* A remoting interface using the JSON-RPC protocol
* The :mod:`Administration Web Interface <django.contrib.admin>` that Django
  gives us for free

We'll start by taking a look at the Database the Models and the database
structure that they generate.

.. toctree::
   :maxdepth: 2

   models
   interface
   CustomRpcScripts
   RPCProtocolChanges
