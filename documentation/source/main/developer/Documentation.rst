=============
Documentation
=============

There are two different ways to view the test API documentation.

The more complete (for now) way is to use Pydoc.  The less complete
(but new) way is to generate the HTML documentation.

Pydoc
=====

Set your Python path to one directory before your autotest path,
then start the pydoc web server on a port of your choosing.

For example, if your autotest installation is in /usr/local/autotest,
then:

::

    $ export PYTHONPATH=/usr/local
    $ pydoc -p 8888

Now use a browser to visit [http://localhost:8888](http://localhost:8888).

This will show all of the Python modules on your system.  Click
on the autotest entry.  Explore from there.


Generate the HTML API documentation
===================================

The new approach (still in progress), is to generate the API docs
as html.  The HTML docs are nicer looking than the Pydoc webserver
ones, but are not yet as complete.

Here [is an example](http://justinclift.fedorapeople.org/autotest_docs/), generated on 6th Aug 2013.

Instructions to generate your own, known to work on Fedora 19:

::

    $ sudo yum -y install MySQL-python python-django python-sphinx
    $ cd /usr/local/autotest
    $ python setup.py build_doc
    running build_doc
    Running Sphinx v1.1.3
    loading pickled environment... done
    building [html]: targets for 0 source files that are out of date
    updating environment: 0 added, 4 changed, 0 removed
    Traceback (most recent call last):istro_detection                                                                                 
      File "/usr/lib/python2.7/site-packages/sphinx/ext/autodoc.py", line 321, in import_object
        __import__(self.modname)
    ImportError: No module named Probe
    reading sources... [100%] frontend/tko_models                                                                                     
    /usr/local/autotest/documentation/source/client/distro_detection.rst:91: WARNING: autodoc can't import/find data 'Probe.CHECK_VERSION_REGEX', it reported error: "No module named Probe", please check your spelling and sys.path
    looking for now-outdated files... none found
    pickling environment... done
    checking consistency... done
    preparing documents... done
    writing output... [100%] index                                                                                                    
    writing additional files... (4 module code pages) _modules/index
     genindex py-modindex search
    copying static files... done
    dumping search index... done
    dumping object inventory... done
    build succeeded, 1 warning.

The generated docs should now be in /usr/local/autotest/build/sphinx/html/.
