"""\
Logic for control file generation.
"""

__author__ = 'showard@google.com (Steve Howard)'

import os
import frontend.settings

AUTOTEST_DIR = os.path.abspath(os.path.join(
    os.path.dirname(frontend.settings.__file__), '..'))


CLIENT_KERNEL_TEMPLATE = """\
def step_init():
	job.next_step([step_test])
	testkernel = job.kernel('%(kernel)s')
	%(kernel_config_line)s
	testkernel.install()
	testkernel.boot(args='%(kernel_args)s')

def step_test():
"""

SERVER_KERNEL_TEMPLATE = """\
kernel_install_control = \"""
%s	pass
\"""

at = autotest.Autotest()
def install_kernel(machine):
	host = hosts.SSHHost(machine)
	at.run(kernel_install_control, host=host)
job.parallel_simple(install_kernel, machines)

""" % CLIENT_KERNEL_TEMPLATE


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


def get_kernel_stanza(kernel, platform=None, kernel_args='', is_server=False):
	if is_server:
		template = SERVER_KERNEL_TEMPLATE
		indent = ''
	else:
		template = CLIENT_KERNEL_TEMPLATE
		indent = '\t'

	stanza = template % {
	    'kernel' : kernel,
	    'kernel_config_line' : kernel_config_line(kernel, platform),
	    'kernel_args' : kernel_args}
	return stanza, indent


def get_tests_stanza(tests):
	return ''.join(read_control_file(test) for test in tests)


def indent_text(text, indent):
	lines = [indent + line for line in text.splitlines()]
	return '\n'.join(lines)


def generate_control(tests, kernel=None, platform=None, is_server=False):
	control_file = ''
	indent = ''
	if kernel:
		control_file, indent = get_kernel_stanza(kernel, platform,
							 is_server=is_server)
	control_file += indent_text(get_tests_stanza(tests), indent)
	return control_file
