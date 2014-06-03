Web Frontend Development
========================

When we run a production Autotest server, we run the Django server
through Apache and serve a compiled version of the GWT client. For
development, however, this is far too painful, and we go through a
completely different setup.

Basic setup
-------------------------
Steps below assume that you have basic software setup. Make sure you run
beforehand: installation_support/autotest-install-package-deps and installation_support/autotest-database-turnkey. On a new environment good validation step is to run unit tests before proceeding.


Django server development
-------------------------

You can read more about Django development at their `documentation
site <http://www.djangoproject.com/documentation/0.96/>`_, but here's
the short version. 

Without Eclipse
'''''''''''''''
-  Running ``manage.py runserver`` will start a development server on
   `http://localhost:8000 <http://localhost:8000/>`_. This server
   automatically reloads files when you change them. You can also view
   stdout/stderr from your Django code right in the console. There's not
   a whole lot you can do from your browser with this server by itself,
   since the only interface to it is through RPCs.
-  ``manage.py test`` will run the server test suite (implemented in
   ``frontend/afe/test.py``). This includes running ``pylint`` on all
   files in ``frontend/afe/`` (checking for errors only), running
   doctests found in the code, and running the extended doctests in
   ``frontend/afe/doctests``. This suite is pretty good at catching
   errors, and you should definitely make sure it passes before
   submitting patches (and please add to it if you add new features).
   Note you may need to install pylint (Ubuntu package
   python2.4-pylint).
-  On that note, ``frontend/afe/doctests/rpc_test.txt`` is also the best
   documentation of the RPC interface to the server, so it's a pretty
   good place to start in understanding what's going on. It's purposely
   written to be readable as documentation, so it doesn't contain tests
   for all corner cases (such as error cases). Such tests should be
   written eventually, but they don't exist now, and if you write some,
   please place them in a separate file so as to keep ``rpc_test.txt``
   readable.
-  You can test the RPC interface out by hand from a Python interpreter:

   ::

       >>> import common
       >>> from frontend.afe import rpc_client_lib
       >>> proxy = rpc_client_lib.get_proxy('http://localhost:8000/afe/server/rpc/', headers={})
       >>> proxy.get_tests(name='sleeptest')
       [{u'description': u'Just a sleep test.', u'test_type': u'Client', u'test_class': u'Kernel', u'path': u'client/tests/sleeptest/control', u'id': 1, u'name': u'sleeptest'}]

With Eclipse
''''''''''''
-  First make sure that you have Eclpise working with PyDev (http://pydev.org/index.html)
-  In Eclipse create django project wrapping frontend; 
 -  File>New>Other...>PyDev>PyDev Django Project; click Next
 -  Project Contents, uncheck Use default and specify directory ``autotest/frontend``, Next 
    few times to set all properties
 -  Now you can use Debug As>PyDev: Django that will start your server in debug mode; 
    You can use standard Eclipse facilities: breakpoints, watches, etc

Note that in both cases when django app is running you can use the admin interface locally
by navigating to http://localhost:8000/afe/server/admin/; This allows to easily add some test
data, examine existing records etc. Note that static files are not served properly so it
is a big ugly but usable.

GWT client development
----------------------

Again, the full scoop can be found in the `GWT Developer
Guide <http://code.google.com/webtoolkit/documentation/>`_, but here's
the short version:

Without Eclipse
'''''''''''''''
-  ``frontend/client/AfeClient-shell`` runs a GWT development shell.
   This runs the client in a JRE in a modified browser widget. It will
   connect to the Django server and operate just like the production
   setup, but it's all running as a normal Java program and it compiles
   on-demand, so you'll never need to compile, you can use your favorite
   Java debugger, etc.
-  Exception tracebacks are viewable in the console window, and you can
   print information to this console using ``GWT.log()``.
-  Hitting reload in the browser window will pull in and recompile any
   changes to the Java code.

With Eclipse
''''''''''''
-  First download and install GWT and Eclipse plug in and make sure 
   all is working by running sample GWT app 
   (https://developers.google.com/web-toolkit/usingeclipse)
-  Change the settings in autotest global_config.ini file by turning on 
   sql_debug_mode: True (section [AUTOTEST_WEB]); This will run 
   frontend application in debug mode and forward calls to GWT running 
   in debug mode (in addition to prining sql statements as name implies).
-  Start the django app as described above by running ``manage.py runserver`` 
   in frontend directory on default port 8000
-  The ``frontend/client/`` directory contains ``.project`` and
   ``.classpath`` files for Eclipse, so you should be able to import the
   project using File->Import...->Existing Project into Workspace.
-  Double check the project properties:
 -  Google->Web Application 'This project has a WAR directory' should 
    be unchecked
 -  Google->Web Toolkit 'Use Google Web Toolkit' should be checked and
    project connected to appropriate GWT
 -  Java Build Path->Libraries tab: remove existing (probably bogus) 
    gwt jar files references and click Add Library-> choose Google Web Toolkit
-  Create a run configuration  
 -  Choose 'Debug Configurations...' from the menu
 -  Click New under (Google) Web Application, give it a name, e.g. AfeFrontEnd
 -  Main tab: Project AfeClient; Main class: com.google.gwt.dev.GWTShell (default)
 -  GWT tab: URL: autotest.AfeClient/AfeClient.html
 -  Common tab: optionally set Display in favorites menu
-  Start debugging AfeFrontEnd configuration
-  Open in a browser url: 127.0.0.1:8000/afe/server/autotest.AfeClient/AfeClient.html?gwt.codesvr=127.0.0.1:9997 Note is is important to use 8000
   (django port) and not 8888 GWT port
-  At this point you can use normal debugging facilities of Eclipe: 
   set breakpoints, watches, etc
-  Note that ``frontend/client/AfeClient.launch`` is not working at the 
   moment and needs to be updated

See Also
--------

-  `AutotestServerInstall <../sysadmin/AutotestServerInstall>`
