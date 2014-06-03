Submission common problems
==========================

These are quick notes to help you fix common problems autotest/virt-test code
submissions usually have. Please read this and keep it in mind when writing
code for these projects:

Gratuitous use of shell script inside a python program
------------------------------------------------------

While we understand that sometimes the contributions in question are adaptations
of existing shell scripts, we ask you to avoid needlessly use shell script
constructs that can be easily replaced by standard python API. Common cases:

1) Use of rm, when you can use os.remove(), and rm -rf when you can use
   shutil.rmtree.

Please don't

::

    os.system('rm /tmp/foo')

Do

::

    os.remove('/tmp/foo')

Please don't

::

    os.system('rm -rf /tmp/foo')

Do

::

    shutil.rmtree('/tmp/foo')


2) Use of cat when you want to write contents to a file

Please, really, don't

::

            cmd = """cat << EOF > %s
    Hey, this is a multiline text
    to %
    EOF""" % (some_file, some_string)
    commands.getstatusoutput(cmd)

Do

::

        content = """
    Hey, this is a multiline text
    to %s
    """ % some_string
        some_file_obj = open(some_file, 'w')
        some_file_obj.write(content)
        some_file_obj.close()


Use of the commands API, or os.system
-------------------------------------

Autotest already provides utility methods that are preferrable over os.system
or commands.getstatus() and the likes. The APIs are called utils.system, utils.run,
utils.system_output. They raise exceptions in case of a return code !=0, so
keep this in mind (either you pass ignore_status=True or trap an exception
in case you want something different other than letting this exception coalesce
and fail your test).

::

    from autotest.client.shared import error
    from autotest.client import utils

    # Raises exception, use with error.context
    error.context('Disabling firewall')
    utils.system('iptables -F')

    # If you just want the output
    output = utils.system_output('dmidecode')

    # Gives a cmdresult object, that has .stdout, .stderr attributes
    cmdresult = utils.run('lspci')
    if not "MYDEVICE" in cmdresult.stdout():
        raise error.TestError("Special device not found")


Use of backslashes
------------------

In general the use of backslashes is really ugly, and it can be avoided pretty
much every time. Please don't use

::

    long_cmd = "foo & bar | foo & bar | foo & bar | foo & bar | foo & bar \
                foo & bar"

instead, use

::

    long_cmd = ("foo & bar | foo & bar | foo & bar | foo & bar | foo & bar "
                "foo & bar")

So, parentheses can avoid the use of backslashes in long lines and commands.


Use of constructs that appeared in versions of python > 2.4
-----------------------------------------------------------

Autotest projects use strictly python 2.4, so you can't use constructs that
appeared in newer versions of python, some examples:

::

    try:
        foo()
    except BarError as details: # except ExceptionClass as variable was introduced after 2.4
        baz

::

    try:
        foo()
    except BarError, details: # correct, 2.4 compliant syntax
        baz()
    finally: # This is the problem, try/except/finally blocks were introduced after 2.4
        gnu()

So, when in doubt, consult the python documentation before sending the patch.

Unconditional import of external python libraries
-------------------------------------------------

Sometimes, for a tiny feature inside the test suite, people import an external,
lesser known python library, on a very central and proeminent part of the framework.

Please, don't do it. You are breaking other people's workflow and that is bad.

The correct way of doing this is conditionally importing the library, setting
a top level variable that indicates whether the feature is active in the system
(that is, the library can be imported), and when calling the specific feature,
check the top level variable to see if the feature could be found. If it couldn't,
you fail the test, most probably by throwing an autotest.client.shared.error.TestNAError.

So, instead of doing:

::

    import platinumlib
    ...
    platinumlib.destroy_all()


You will do:

::

    PLATINUMLIB_ENABLED = True
    try:
        import platinumlib
    except ImportError:
        PLATINUMLIB_ENABLED = False
    ...
    if not PLATINUMLIB_ENABLED:
        raise error.TestNAError('Platinum lib is not installed. '
                                'You need to install the package '
                                'python-platinumlib for this test '
                                'to work.')
    platinumlib.destroy_all()

Any patch that carelessly sticks external library imports in central libraries of
virt-test for optional features will be downright rejected.
