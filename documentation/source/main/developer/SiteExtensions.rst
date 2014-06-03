===============================
Adding site-specific extensions
===============================

If you need to extend the Autotest code in a way that isn't usable by
the main project, then you'll probably want to do so in a way that
doesn't unduly complicate merging your local, extended code with the
official project code. In general this means that you want to pull any
site-specific code into separate files, and have the main code call into
the extension in an optional way.

For site-specific tests this is not a problem. Each test should be
self-contained in its own directory and so you should be able to add new
tests without any other changes to Autotest at all. There may
occasionally be a conflict if a new test is added to the project that
conflicts with a private name you're already using, but this will should
not be overly common and is easily fixed by renaming.

For adding site-specific common libraries, this is also not a big
problem. Add your module to the client/common\_lib directory but add the
name of your module to client/common\_lib/site\_libraries.py instead of
directly to client/common\_lib/&#95;&#95;init&#95;&#95;.py. This will
create a small conflict as your local
client/common\_lib/site\_libraries.py will differ from the official one,
however since the official one should never really be changing, merging
should never be a problem. However, remember that any code that imports
these site-specific libraries has itself become site-specific.

In any other cases where you have to modify the core Autotest code,
you'll have to make an effort to separate out your extensions from the
main body of code. Assuming your extension is being done in a file x.py,
the easiest way to extend it is to add a new module site\_x.py that
contains your site specific-code, and then add code to x.py that imports
site\_x and makes the appropriate calls.

Now, you'll want to be able to push out these calls to site\_x into the
official code so that you don't have to constantly merge around them.
That means you'll still have to be careful about how you use site\_x. In
particular:

#. the import of site\_x has to be done in such a way the code still
   works properly when site\_x doesn't exist
#. the coupling between x and site\_x should be as minimal as possible
   (to reduce the chances that other people's changes to x inadvertently
   break site\_x)

As an example, look at the use of site\_kernel in client/bin/kernel.py.
It supports point 1 by pulling in a function from site\_kernel, and if
the import of site\_kernel fails, it provides a default implementation
of the function it is trying to import. It supports point 2 by only
inserting a single call into auto\_kernel stage, one with very clear and
simple semantics (i.e. perform some optional, site-specific munging of
path names before using them).

Adding site-specific extensions to the CLI
------------------------------------------

If you need to change the default behavior of some autotest-rpc-client commands, you
can create a cli/site\_<topic>.py file to subclass some of the classes
from cli/<topic>.py.

The following example would prevent the creation of platform labels:

::

    import inspect, new, sys

    from autotest_lib.cli import topic_common, label


    class site_label(label.label):
        pass


    class site_label_create(label.label_create):
        """Disable the platform option
        autotest-rpc-client label create <labels>|--blist <file>"""
        def __init__(self):
            super(site_label_create, self).__init__()
            self.parser.remove_option("--platform")


        def parse(self):
            (options, leftover) = super(site_label_create, self).parse()
            self.is_platform = False
            return (options, leftover)


    # The following boiler plate code should be added at the end to create
    # all the other site_<topic>_<action> classes that do not modify their
    # <topic>_<action> super class.

    # Any classes we don't override in label should be copied automatically
    for cls in [getattr(label, n) for n in dir(label) if not n.startswith("_")]:
        if not inspect.isclass(cls):
            continue
        cls_name = cls.__name__
        site_cls_name = 'site_' + cls_name
        if hasattr(sys.modules[__name__], site_cls_name):
            continue
        bases = (site_label, cls)
        members = {'__doc__': cls.__doc__}
        site_cls = new.classobj(site_cls_name, bases, members)
        setattr(sys.modules[__name__], site_cls_name, site_cls)
