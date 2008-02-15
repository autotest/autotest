import os, doctest, glob, sys
import django.test.utils, django.test.simple
from frontend import settings, afe

# doctest takes a copy+paste log of a Python interactive session, runs a Python
# interpreter, and replays all the inputs from the log, checking that the
# outputs all match the log.  This allows us to easily test behavior and
# document functions at the same time, since the log shows exactly how functions
# are called and what their outputs look like.  See
# http://www.python.org/doc/2.4.3/lib/module-doctest.html for more details.

# In this file, we run doctest on all files found in the doctests/ directory.
# We use django.test.utils to run the tests against a fresh test database every
# time.

app_name = 'afe'
doctest_dir = 'doctests'
doctest_paths = [os.path.join(doctest_dir, filename) for filename
		 in os.listdir(os.path.join(app_name, doctest_dir))]

modules = []
module_names = [os.path.basename(filename)[:-3]
		for filename in glob.glob(app_name + '/*.py')
		if '__init__' not in filename and 'test.py' not in filename]
for module_name in module_names:
	__import__('frontend.afe', globals(), locals(), [module_name])
	modules.append(getattr(afe, module_name))

print_after = 'Ran %d tests from %s'


def run_tests(module_list, verbosity=1):
	total_errors = run_pylint()
	old_db = settings.DATABASE_NAME
	django.test.utils.setup_test_environment()
	django.test.utils.create_test_db(verbosity)
	try:
		for module in modules:
			failures, test_count = doctest.testmod(module)
			print print_after % (test_count, module.__name__)
			total_errors += failures
		for path in doctest_paths:
			failures, test_count = doctest.testfile(path)
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


pylint_opts = {
    'models': ['--disable-msg=E0201'],
    'rpc_client_lib': ['--disable-msg=E0611'],
}

pylint_base_opts = ['--disable-msg-cat=warning,refactor,convention',
		    '--reports=no']

pylint_exclude = ['management']


def run_pylint():
	try:
		import pylint.lint
	except ImportError:
		print 'pylint not installed'
		return
	original_dir = os.getcwd()
	os.chdir('..')
	total_errors = 0
	for module in modules:
		module_name = module.__name__
		module_basename = module_name.split('.')[-1]
		if module_basename in pylint_exclude:
			continue
		print 'Checking ' + module_name
		opts = (pylint_base_opts + pylint_opts.get(module_basename, []))
		full_args = opts + [module_name]
		result = pylint.lint.Run(full_args)
		errors = result.linter.stats['error']
		total_errors += errors
	os.chdir(original_dir)
	return total_errors
