============================================
Autotest Web Frontend Implementation details
============================================

Here we outline the building blocks and implementation details of the autotest
web interface.

Overview
--------

Here's a broad overview of how the system fits together:

[[FrontendImplementationDetails/frontend_overview.png]]

-  The **Django RPC server** is an RPC server, written using the Django
   framework. It functions as a web server, accepting RPCs as HTTP POST
   requests, querying the MySQL database as necessary, and returning
   results. In a production environment, it runs within Apache using
   mod\_python

   -  The AFE server code lives under ``frontend/afe`` and uses the
      ``autotest_web`` database.
   -  The TKO server code lives under ``new_tko/tko`` and uses the
      ``tko`` database.
   -  In both servers, the RPC entry points are defined in
      ``rpc_interface.py``.
   -  All RPC POST requests go to a single URL,
      ``(afe|new_tko)/server/rpc/``. They get dispatched to RPC methods
      by the code in ``rpc_handler.py``. See `Django
      documentation <http://docs.djangoproject.com/en/dev/>`_ for an
      explanation of how HTTP requests get mapped to Python code using
      URLconfs.
   -  Database models live in ``models.py``. See `Django
      documentation <http://docs.djangoproject.com/en/dev/>`_ for an
      explanation of models.

-  **RPC calls** and responses are encoded according to the JSON-RPC
   protocol.

   -  JSON is a simple data representation format based on Javascript.
      See `http://json.org <http://json.org/>`_.
   -  JSON-RPC is a very simple standard for representing RPC calls and
      responses in JSON. See
      `http://jsonrpc.org <http://jsonrpc.org/>`_.
   -  RPCs are made by sending a POST request to the server with the
      POST data containing the JSON-encoded request. The response text
      is a JSON-encoded response.

      -  On the server, the code for serializing JSON lives at
         ``frontend/afe/simplejson``. The code for forming and
         dispatching JSON-RPC requests lives at
         ``frontend/afe/json_rpc``.
      -  The CLI uses the same code for serializing JSON-RPC.
      -  The GWT client uses GWT's builtin JSON library for serializing
         JSON. The code for handling JSON-RPC requests is in
         ``autotest.common.JsonRpcProxy`` and friends.

-  The **GWT client** is a browser-based client for AFE and TKO
   (technically, there are two separate clients). It's written using
   Google Web Toolkit (GWT), a framework for writing browser apps in
   Java and having them compiled to Javascript. See
   `http://code.google.com/webtoolkit <http://code.google.com/webtoolkit>`_.

   -  More details...

-  The **CLI** is a command-line Python application that makes calls to
   the RPC server. It lives under the ``cli`` directory. ``cli/autotest-rpc-client``
   is the main entry point.
