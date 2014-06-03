================================================
Using the Autotest Mock Library for unit testing
================================================

To aid with unit testing, we've implemented a very useful mocking and
stubbing library under ``client/shared/test_utils/mock.py``. This
library can help you with

-  safety stubbing out attributes of modules, classes, or instances, and
   restoring them when the test completes
-  creating mock functions and objects to substitute for real function
   and class instances
-  verifying that code under test interacts with external functions and
   objects in a certain way, without actually depending on external
   objects

Setting up to use the code
--------------------------

::

    from autotest.client.shared.test_utils import mock

You'll often need a ``mock_god`` instance as we'll see later. This is
best done in your setUp method:

::

    class MyTest(unittest.TestCase):
      def setUp(self):
        self.god = mock.mock_god()

As we'll also see later, you'll often want to call
mock\_god.unstub\_all() in your tearDown method, so I'll include that
here too:

::

      def tearDown(self):
        self.god.unstub_all()

Stubbing out attributes
-----------------------

Say we want to make os.path.exists() always return True for a test.
First, we can create a mock function:

::

    mock_exists = mock.mock_function('os.path.exists', default_return_val=True)

This returns a function (actually it's a callable object, but no matter)
that will accept any arguments and always returns True. The function
name passed in ('os.path.exists') is used only for error messages and
can be anything you find helpful. Next, we want to stub out
os.path.exists with our new function:

::

    self.god.stub_with(os.path, 'exists', mock_exists)

Now you can call the code under test, and when it calls os.path.exists
it'll actually be calling your mock function. Note that ``stub_with``
can accept any object to use as a stub -- it doesn't have to be a
``mock_function``. You could define your own function to do actual work,
but that's rarely necessary.

Calling ``self.god.unstub_all()`` will restore ``os.path.exists`` to
it's original value. **You must remember to always do this at the end of
your test.** Even if your test never needs it to be unstubbed, your test
may be combined with others in a single test run, and you could mess up
those other tests if you don't clean up your stubs. The best way to do
this is to **always call ``unstub_all()`` in your ``tearDown`` method**
if you're using stubbing.

Stubbing methods on classes
---------------------------

The above approach won't work for stubbing out methods on classes (not
instances, but the classes themselves). You'll need to use the trick of
wrapping the mock function in ``staticmethod()``:

::

    self.god.stub_with(MyClass, 'my_method', staticmethod(mock_method))

Verifying external interactions of code under test
--------------------------------------------------

The above trick is nice, but what if you need to ensure the code under
tests calls your mock functions in a certain way? For that, you can use
``mock_god.create_mock_function``.

::

    mock_exists = self.god.create_mock_function('os.path.exists')
    self.god.stub_with(os.path, 'exists', mock_exists)
    # note that stub_function() would be more convenient here - see below

How is this different from the above? Mock functions created using
``mock_god.create_mock_function`` follow the *expect/verify* model. The
basic outline of this is as follows:

-  Create your mock functions.
-  Set up the expected call sequence on those functions.
-  Run the code under test.
-  Verify that the mock functions were called as expected.

Let's look at an example, following from the snippet above:

::

    # return True the first time it's called
    os.path.expect_call('/my/directory').and_return(True)
    # return False the next time it's called
    os.path.expect_call('/another/directory').and_return(False)
    # run the code under test
    function_under_test()
    # ensure the code under test made the calls we expected
    self.god.check_playback()

This tells the mock god to expect a call to os.path.exists with the
argument ``'/my/directory'`` and then with ``'/another/directory'``. If
the code under tests makes these calls in this order, it will get the
specified return values and ``check_playback()`` will return without
error. ``check_playback()`` will raise an exception if any of the
following occurred:

-  a mock function was called with the wrong arguments
-  a mock function was called when it wasn't supposed to be
-  a mock function was not called when it was expected to be

Note that order must be consistent across all mock functions (remember
god knows all)

Constructing mock class instances
---------------------------------

Frequently our code under test will expect an object to be passed in,
and we'll want to mock out every method on that object. In that case we
can use ``mock_god.create_mock_class``:

::

    mock_data_source = self.god.create_mock_class(DataSource, 'mock_data_source')
    mock_data_source.get_data.expect_call().and_return('some data') # method taking no parameters
    mock_data_source.put_data.expect_call(1) # void method
    function_under_test(mock_data_source)
    self.god.check_playback()

This code creates a mock instance of ``DataSource``. On the mock
instance, *all public methods* of ``DataSource`` will be replaced with
mock functions on which you can use the expect/verify model, just like
functions created with ``create_mock_function``. The second argument to
``create_mock_class`` can be any name; it's just used in the debug
output.

Isolating a method from other methods on the same instance
----------------------------------------------------------

You may find yourself needing to test a method of a class instance and
wanting to mock out every other method of that instance.
``mock_god.mock_up()`` provides a convenient way to do this:

::

    # construct a real DataSource
    data_source = DataSource()
    # replace every method with a mock function
    self.god.mock_up(data_source, "data_source")
    data_source.get_data.expect_call().and_return('data')
    data_source.put_data.expect_call('more data')
    # run a real method on the instance
    data_source.do_data_manipulation.run_original_function()
    # do_data_manipulation() calls get_data() and put_data()
    self.god.check_playback()

Unlike ``create_mock_class``, ``mock_up`` takes an existing instance and
replaces all methods (that don't start with '\_\_') with mock functions,
while retaining the ability to run the original functions through
``run_original_function()``. Unlike create\_mock\_class it will mock up
functions for "protected" (starting with '\_') methods.

Verifying class creation within code under test
-----------------------------------------------

What if your code under test instantiates and uses a class, and you want
to mock out that class but never have access to it? In this case you can
stub out the class itself using ``mock_god.create_mock_class_obj``. I'll
use ``subprocess.Popen`` as an example:

::

    MockPopen = self.god.create_mock_class_obj(subprocess.Popen)
    self.god.stub_with(subprocess, 'Popen', MockPopen)
    # expect creation of a Popen object
    proc = subprocess.Popen.expect_new('some command', shell=True)
    # expect a call on the created Popen object
    proc.poll.expect_call().and_return(0)
    # code under test creates a subprocess.Popen object and uses it
    function_under_test()
    self.god.check_playback()

Convenient shortcuts for stubbing
---------------------------------

``stub_function`` automatically stubs out a function with a mock
function created using ``mock_god.create_mock_function``, so that you
can use the expect/verify model on it.

::

    self.god.stub_function(os.path, 'exists')
    # this is equivalent to:
    mock_exists = self.god.create_mock_function('exists')
    self.god.stub_with(os.path, 'exists', mock_exists)

``stub_class_method`` does the same thing, but wraps the mock function
in ``staticmethod()`` and thus is suitable for class methods.

::

    self.god.stub_class_method(MyClass, 'my_method')
    # this is equivalent to:
    mock_method = self.god.create_mock_function('my_method')
    self.god.stub_with(MyClass, 'my_method', staticmethod(mock_method))

Stubbing out builtins
---------------------

Often we'll want to stub out a builtin function like ``open()``. We've
found that the best way to do this is to set an attribute on the module
under test, rather than try to mess with ``__builtins__`` or anything,
as that can mess up other code (such as test infrastructure code).

::

    self.god.stub_function(module_under_test, 'open')
    # note we're using StringIO to fake a file object
    module_under_test.open.expect_call('/some/path', 'r').and_return(StringIO.StringIO('file text'))

    module_under_test.function_under_test() # tries to call builtin open
    self.god.check_playback()

