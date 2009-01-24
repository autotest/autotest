"""\
Logic for control file generation.
"""

__author__ = 'showard@google.com (Steve Howard)'

import re, os

import common
from autotest_lib.frontend.afe import model_logic
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
    if len(kernel_list) > 1:
        job.set_run_number(1)  # Include run numbers in output directory names.
        job.show_kernel_in_test_tag(True)  # Include kernel in output dir name.

def boot_kernel(kernel_version):
    testkernel = job.kernel(kernel_version)
    %(kernel_config_line)s
    testkernel.install()
    testkernel.boot(args='%(kernel_args)s')

def step_test(kernel_version):
    global kernel
    kernel = kernel_version  # Set the global in case anyone is using it.
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


def get_tests_stanza(tests, is_server, prepend=None, append=None,
                     client_control_file=''):
    """ Constructs the control file test step code from a list of tests.

    @param tests A sequence of test control files to run.
    @param is_server bool, Is this a server side test?
    @param prepend A list of steps to prepend to each client test.
        Defaults to [].
    @param append A list of steps to append to each client test.
        Defaults to [].
    @param client_control_file If specified, use this text as the body of a
        final client control file to run after tests.  is_server must be False.

    @returns The control file test code to be run.
    """
    assert not (client_control_file and is_server)
    if not prepend:
        prepend = []
    if not append:
        append = []
    raw_control_files = [read_control_file(test) for test in tests]
    return _get_tests_stanza(raw_control_files, is_server, prepend, append,
                             client_control_file=client_control_file)


def _get_tests_stanza(raw_control_files, is_server, prepend, append,
                      client_control_file=''):
    """
    Implements the common parts of get_test_stanza.

    A site_control_file that wants to implement its own get_tests_stanza
    likely wants to call this in the end.

    @param raw_control_files A list of raw control file data to be combined
        into a single control file.
    @param is_server bool, Is this a server side test?
    @param prepend A list of steps to prepend to each client test.
    @param append A list of steps to append to each client test.
    @param client_control_file If specified, use this text as the body of a
        final client control file to append to raw_control_files after fixups.

    @returns The combined mega control file.
    """
    if is_server:
        return '\n'.join(prepend + raw_control_files + append)
    if client_control_file:
        # 'return locals()' is always appended incase the user forgot, it
        # is necessary to allow for nested step engine execution to work.
        raw_control_files.append(client_control_file + '\nreturn locals()')
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
    for profiler in profilers:
        prepend.append("job.profilers.add('%s')" % profiler.name)
        append.append("job.profilers.delete('%s')" % profiler.name)
    return prepend, append


def split_kernel_list(kernel_string):
    """Split the kernel(s) string from the user into a list of kernels.

    We allow multiple kernels to be listed separated by a space or comma.
    """
    return re.split('[\s,]+', kernel_string.strip())


def _sanity_check_generate_control(is_server, client_control_file, kernel):
    """
    Sanity check some of the parameters to generate_control().

    This exists as its own function so that site_control_file may call it as
    well from its own generate_control().

    @raises ValidationError if any of the parameters do not make sense.
    """
    if is_server and client_control_file:
        raise model_logic.ValidationError(
                {'tests' : 'You cannot run server tests at the same time '
                 'as directly supplying a client-side control file.'})


def generate_control(tests, kernel=None, platform=None, is_server=False,
                     profilers=(), client_control_file=''):
    """
    Generate a control file for a sequence of tests.

    @param tests A sequence of test control files to run.
    @param kernel A string listing one or more kernel versions to test
        separated by spaces or commas.
    @param platform A platform object with a kernel_config attribute.
    @param is_server bool, Is this a server control file rather than a client?
    @param profilers A list of profiler objects to enable during the tests.
    @param client_control_file Contents of a client control file to run as the
        last test after everything in tests.  Requires is_server=False.

    @returns The control file text as a string.
    """
    _sanity_check_generate_control(is_server=is_server, kernel=kernel,
                                   client_control_file=client_control_file)

    control_file_text = ''
    if kernel:
        kernel_list = split_kernel_list(kernel)
        control_file_text = get_kernel_stanza(kernel_list, platform,
                                              is_server=is_server)
    elif not is_server:
        control_file_text = CLIENT_EMPTY_TEMPLATE

    prepend, append = _get_profiler_commands(profilers, is_server)

    control_file_text += get_tests_stanza(tests, is_server, prepend, append,
                                          client_control_file)
    return control_file_text
