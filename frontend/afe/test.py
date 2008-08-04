import common
import os, doctest, glob, sys
import django.test.utils, django.test.simple
from autotest_lib.frontend import settings, afe

# doctest takes a copy+paste log of a Python interactive session, runs a Python
# interpreter, and replays all the inputs from the log, checking that the
# outputs all match the log.  This allows us to easily test behavior and
# document functions at the same time, since the log shows exactly how functions
# are called and what their outputs look like.  See
# http://www.python.org/doc/2.4.3/lib/module-doctest.html for more details.

# In this file, we run doctest on all files found in the doctests/ directory.
# We use django.test.utils to run the tests against a fresh test database every
# time.

app_dir = os.path.dirname(__file__)
doctest_dir = os.path.join(app_dir, 'doctests')
doctest_paths = [os.path.join(doctest_dir, filename) for filename
                 in os.listdir(doctest_dir)
                 if not filename.startswith('.')
                 if not filename.endswith('~')]
doctest_paths.sort()

def get_modules():
    modules = []
    module_names = [os.path.basename(filename)[:-3]
                    for filename in glob.glob(os.path.join(app_dir, '*.py'))
                    if '__init__' not in filename
                    and 'test.py' not in filename]
    for module_name in module_names:
        mod = common.setup_modules.import_module(module_name, 'frontend.afe')
        modules.append(mod)
    return modules


print_after = 'Ran %d tests from %s'


def run_tests(module_list=[], verbosity=1):
    """
    module_list is ignored - we're just required to have this signature as a
    Django test runner.
    """
    modules = get_modules()
    total_errors = 0
    old_db = settings.DATABASE_NAME
    django.test.utils.setup_test_environment()
    django.test.utils.create_test_db(verbosity)
    try:
        for module in modules:
            failures, test_count = doctest.testmod(module)
            print print_after % (test_count, module.__name__)
            total_errors += failures
        for path in doctest_paths:
            failures, test_count = doctest.testfile(path, module_relative=False)
            print print_after % (test_count, path)
            total_errors += failures
    finally:
        django.test.utils.destroy_test_db(old_db)
        django.test.utils.teardown_test_environment()
    print
    if total_errors == 0:
        print 'OK'
    else:
        print 'FAIL: %d errors' % total_errors
    return total_errors
