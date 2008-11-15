"""\
Logic for control file generation.
"""

__author__ = 'showard@google.com (Steve Howard)'

import re, os
import frontend.settings

AUTOTEST_DIR = os.path.abspath(os.path.join(
    os.path.dirname(frontend.settings.__file__), '..'))

CLIENT_EMPTY_TEMPLATE = 'def step_init():\n'

CLIENT_KERNEL_TEMPLATE = """\
kernel_list = %(kernel_list)r

def step_init():
    for kernel_version in kernel_list:
        job.next_step(boot_kernel, kernel_version)
        job.next_step(step_test, kernel_version)

def boot_kernel(kernel_version):
    testkernel = job.kernel(kernel_version)
    %(kernel_config_line)s
    testkernel.install()
    testkernel.boot(args='%(kernel_args)s')

def step_test(kernel_version):
    global kernel
    kernel = kernel_version  # Set the global in case anyone is using it.
    if len(kernel_list) > 1:
        job.set_test_tag_prefix(kernel_version)  # Separate output by kernel.
"""

SERVER_KERNEL_TEMPLATE = """\
kernel_list = %%(kernel_list)r
kernel_install_control = \"""
%s    pass
\"""

at = autotest.Autotest()
def install_kernel(machine):
    host = hosts.create_host(machine)
    at.run(kernel_install_control, host=host)
job.parallel_simple(install_kernel, machines)

""" % CLIENT_KERNEL_TEMPLATE

CLIENT_STEP_TEMPLATE = "    job.next_step('step%d')\n"


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


def get_kernel_stanza(kernel_list, platform=None, kernel_args='',
                      is_server=False):
    if is_server:
        template = SERVER_KERNEL_TEMPLATE
    else:
        template = CLIENT_KERNEL_TEMPLATE

    stanza = template % {
        'kernel_list' : kernel_list,
        # XXX This always looks up the config line using the first kernel
        # in the list rather than doing it for each kernel.
        'kernel_config_line' : kernel_config_line(kernel_list[0], platform),
        'kernel_args' : kernel_args}
    return stanza


def add_boilerplate_to_nested_steps(lines):
    # Look for a line that begins with 'def step_init():' while
    # being flexible on spacing.  If it's found, this will be
    # a nested set of steps, so add magic to make it work.
    # See client/bin/job.py's step_engine for more info.
    if re.search(r'^(.*\n)*def\s+step_init\s*\(\s*\)\s*:', lines):
        lines += '\nreturn locals() '
        lines += '# Boilerplate magic for nested sets of steps'
    return lines


def format_step(item, lines):
    lines = indent_text(lines, '    ')
    lines = 'def step%d():\n%s' % (item, lines)
    return lines


def get_tests_stanza(tests, is_server, prepend=None, append=None):
    """Constructs the control file test step code from a list of tests.

    Args:
      tests: A sequence of test control files to run.
      is_server: Boolean - is this a server side test?
      prepend: A list of steps to prepend to each client test.  Defaults to [].
      append: A list of steps to append to each client test.  Defaults to [].
    Returns:
      The control file test code to be run.
    """
    if not prepend:
        prepend = []
    if not append:
        append = []
    raw_control_files = [read_control_file(test) for test in tests]
    return _get_tests_stanza(raw_control_files, is_server, prepend, append)


def _get_tests_stanza(raw_control_files, is_server, prepend, append):
    if is_server:
        return '\n'.join(raw_control_files)
    raw_steps = prepend + [add_boilerplate_to_nested_steps(step)
                           for step in raw_control_files] + append
    steps = [format_step(index, step)
             for index, step in enumerate(raw_steps)]
    header = ''.join(CLIENT_STEP_TEMPLATE % i for i in xrange(len(steps)))
    return header + '\n' + '\n\n'.join(steps)


def indent_text(text, indent):
    lines = [indent + line for line in text.splitlines()]
    return '\n'.join(lines)


def _get_profiler_commands(profilers, is_server):
    prepend, append = [], []
    if is_server:
        return prepend, append
    for profiler in profilers:
        prepend.append("job.profilers.add('%s')" % profiler.name)
        append.append("job.profilers.delete('%s')" % profiler.name)
    return prepend, append


def split_kernel_list(kernel_string):
    """Split the kernel(s) string from the user into a list of kernels.

    We allow multiple kernels to be listed separated by a space or comma.
    """
    return re.split('[\s,]+', kernel_string.strip())


def generate_control(tests, kernel=None, platform=None, is_server=False,
                     profilers=()):
    """Generate a control file for a sequence of tests.

    Args:
      tests: A sequence of test control files to run.
      kernel: A string listing one or more kernel versions to test separated
          by spaces or commas.
      platform: A platform object with a kernel_config attribute.
      is_server: Boolean - is a server control file rather than a client?
      profilers: A list of profiler objects to enable during the tests.

    Returns:
      The control file text as a string.
    """
    control_file_text = ''
    if kernel:
        kernel_list = split_kernel_list(kernel)
        control_file_text = get_kernel_stanza(kernel_list, platform,
                                              is_server=is_server)
    elif not is_server:
        control_file_text = CLIENT_EMPTY_TEMPLATE

    prepend, append = _get_profiler_commands(profilers, is_server)

    control_file_text += get_tests_stanza(tests, is_server, prepend, append)
    return control_file_text
