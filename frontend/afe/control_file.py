"""\
Logic for control file generation.
"""

__author__ = 'showard@google.com (Steve Howard)'

import os
import frontend.settings

AUTOTEST_DIR = os.path.abspath(os.path.join(
    os.path.dirname(frontend.settings.__file__), '..'))


KERNEL_INSTALL_TEMPLATE = """\
def step_init():
	job.next_step([step_test])
	testkernel = job.kernel('%(kernel)s')
	%(kernel_config_line)s
	testkernel.install()
	testkernel.boot(args='%(kernel_args)s')

def step_test():
"""

def kernel_config_line(kernel, platform):
	if (not kernel.endswith('.rpm') and platform and
	    platform.kernel_config):
		return "testkernel.config('%s')" % platform.kernel_config
	return ''


def read_control_file(test):
	control_file = open(os.path.join(AUTOTEST_DIR, test.path))
	control_contents = control_file.read()
	control_file.close()
	return control_contents


def get_kernel_stanza(kernel, platform, kernel_args):
	return KERNEL_INSTALL_TEMPLATE % {
	    'kernel' : kernel,
	    'kernel_config_line' : kernel_config_line(kernel, platform),
	    'kernel_args' : kernel_args}


def get_tests_stanza(tests):
	return ''.join(read_control_file(test) for test in tests)


def indent_text(text, indent):
	lines = [indent + line for line in text.splitlines()]
	return '\n'.join(lines)


def generate_client_control(tests, kernel=None, platform=None):
	control_file = ''
	indent = ''
	if kernel:
		control_file = get_kernel_stanza(kernel, platform, '')
		indent = '\t'

	control_file += indent_text(get_tests_stanza(tests), indent)
	return control_file


def generate_server_control(tests):
	return get_tests_stanza(tests)
