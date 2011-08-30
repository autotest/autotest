import common
import os, doctest, glob, sys
from django.conf import settings
from django.db import connection
import django.test.utils

# doctest takes a copy+paste log of a Python interactive session, runs a Python
# interpreter, and replays all the inputs from the log, checking that the
# outputs all match the log.  This allows us to easily test behavior and
# document functions at the same time, since the log shows exactly how functions
# are called and what their outputs look like.  See
# http://www.python.org/doc/2.4.3/lib/module-doctest.html for more details.

# In this file, we run doctest on all files found in the doctests/ directory.
# We use django.test.utils to run the tests against a fresh test database every
# time.

class DoctestRunner(object):
    _PRINT_AFTER = 'Ran %d tests from %s'

    def __init__(self, app_dir, app_module_name):
        self._app_dir = app_dir
        self._app_module_name = app_module_name


    def _get_doctest_paths(self):
        doctest_dir = os.path.join(self._app_dir, 'doctests')
        doctest_paths = [os.path.join(doctest_dir, filename) for filename
                         in os.listdir(doctest_dir)
                         if not filename.startswith('.')
                         if not filename.endswith('~')]
        return sorted(doctest_paths)


    def _get_modules(self):
        modules = []
        module_names = [os.path.basename(filename)[:-3]
                        for filename
                        in glob.glob(os.path.join(self._app_dir, '*.py'))
                        if '__init__' not in filename
                        and 'test.py' not in filename]
        # TODO: use common.setup_modules.import_module()
        app_module = __import__(self._app_module_name, globals(), locals(),
                                module_names)
        for module_name in module_names:
            modules.append(getattr(app_module, module_name))
        return modules


    def run_tests(self):
        """
        module_list is ignored - we're just required to have this signature as a
        Django test runner.
        """
        doctest_paths = self._get_doctest_paths()
        modules = self._get_modules()
        total_errors = 0
        old_db = settings.DATABASES['default']['NAME']
        django.test.utils.setup_test_environment()
        connection.creation.create_test_db()
        try:
            for module in modules:
                failures, test_count = doctest.testmod(module)
                print self._PRINT_AFTER % (test_count, module.__name__)
                total_errors += failures
            for path in doctest_paths:
                failures, test_count = doctest.testfile(path,
                                                        module_relative=False)
                print self._PRINT_AFTER % (test_count, path)
                total_errors += failures
        finally:
            connection.creation.destroy_test_db(old_db)
            django.test.utils.teardown_test_environment()
        print
        if total_errors == 0:
            print 'OK'
        else:
            print 'FAIL: %d errors' % total_errors
        return total_errors
