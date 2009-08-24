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

EMPTY_TEMPLATE = 'def step_init():\n'

CLIENT_KERNEL_TEMPLATE = """\
kernel_list = %(client_kernel_list)s

def step_init():
    for kernel_info in kernel_list:
        job.next_step(boot_kernel, kernel_info)
        job.next_step(step_test, kernel_info['version'])
    if len(kernel_list) > 1:
        job.set_run_number(1)  # Include run numbers in output directory names.
        job.show_kernel_in_test_tag(True)  # Include kernel in output dir name.


def boot_kernel(kernel_info):
    testkernel = job.kernel(kernel_info['version'])
    if kernel_info['config_file']:
        testkernel.config(kernel_info['config_file'])
    testkernel.install()

    cmdline = ' '.join((kernel_info.get('cmdline', ''), '%(kernel_args)s'))
    testkernel.boot(args=cmdline)


def step_test(kernel_version):
    global kernel
    kernel = kernel_version  # Set the global in case anyone is using it.
"""

SERVER_KERNEL_TEMPLATE = """\
kernel_list = %%(server_kernel_list)s
kernel_install_control = \"""
%s    pass
\"""

from autotest_lib.client.common_lib import error

at = autotest.Autotest()
def install_kernel(machine, kernel_info):
    host = hosts.create_host(machine)
    at.install(host=host)
    at.run(kernel_install_control %%%%
           {'client_kernel_list': repr([kernel_info])}, host=host)


num_machines_required = len(machines)
if len(machines) > 4:
    # Allow a large multi-host tests to proceed despite a couple of hosts
    # failing to properly install the desired kernel (exclude those hosts).
    # TODO(gps): Figure out how to get and use SYNC_COUNT here.  It is defined
    # within some control files and will end up inside of stepN functions below.
    num_machines_required = len(machines) - 2


def step_init():
    # a host object we use solely for the purpose of finding out the booted
    # kernel version, we use machines[0] since we already check that the same
    # kernel has been booted on all machines
    if len(kernel_list) > 1:
        kernel_host = hosts.create_host(machines[0])

    for kernel_info in kernel_list:
        func = lambda machine: install_kernel(machine, kernel_info)
        good_machines = job.parallel_on_machines(func, machines)
        if len(good_machines) < num_machines_required:
            raise error.TestError(
                    "kernel installed on only %%%%d of %%%%d machines."
                    %%%% (len(good_machines), num_machines_required))

        # Replace the machines list that step_test() will use with the
        # ones that successfully installed the kernel.
        machines[:] = good_machines

        # have server_job.run_test() automatically add the kernel version as
        # a suffix to the test name otherwise we cannot run the same test on
        # different kernel versions
        if len(kernel_list) > 1:
            job.set_test_tag_prefix(kernel_host.get_kernel_ver())
        step_test()


def step_test():
""" % CLIENT_KERNEL_TEMPLATE

CLIENT_STEP_TEMPLATE = "    job.next_step('step%d')\n"
SERVER_STEP_TEMPLATE = '    step%d()\n'


def kernel_config_file(kernel, platform):
    if (not kernel.endswith('.rpm') and platform and
        platform.kernel_config):
        return platform.kernel_config
    return None


def read_control_file(test):
    control_file = open(os.path.join(AUTOTEST_DIR, test.path))
    control_contents = control_file.read()
    control_file.close()
    return control_contents


def get_kernel_stanza(kernel_list, platform=None, kernel_args='',
                      is_server=False):

    template_args = {'kernel_args' : kernel_args}

    # add 'config_file' keys to the kernel_info dictionaries
    new_kernel_list = []
    for kernel_info in kernel_list:
        config_file = kernel_config_file(kernel_info['version'], platform)
        new_kernel_info = dict(kernel_info, config_file=config_file)
        new_kernel_list.append(new_kernel_info)

    if is_server:
        template = SERVER_KERNEL_TEMPLATE
        # leave client_kernel_list as a placeholder
        template_args['client_kernel_list'] = '%(client_kernel_list)s'
        template_args['server_kernel_list'] = repr(new_kernel_list)
    else:
        template = CLIENT_KERNEL_TEMPLATE
        template_args['client_kernel_list'] = repr(new_kernel_list)

    return template % template_args


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
    if client_control_file:
        # 'return locals()' is always appended incase the user forgot, it
        # is necessary to allow for nested step engine execution to work.
        raw_control_files.append(client_control_file + '\nreturn locals()')
    raw_steps = prepend + [add_boilerplate_to_nested_steps(step)
                           for step in raw_control_files] + append
    steps = [format_step(index, step)
             for index, step in enumerate(raw_steps)]
    if is_server:
        step_template = SERVER_STEP_TEMPLATE
        footer = '\n\nstep_init()\n'
    else:
        step_template = CLIENT_STEP_TEMPLATE
        footer = ''

    header = ''.join(step_template % i for i in xrange(len(steps)))
    return header + '\n' + '\n\n'.join(steps) + footer


def indent_text(text, indent):
    """Indent given lines of python code avoiding indenting multiline
    quoted content (only for triple " and ' quoting for now)."""
    regex = re.compile('(\\\\*)("""|\'\'\')')

    res = []
    in_quote = None
    for line in text.splitlines():
        # if not within a multinline quote indent the line contents
        if in_quote:
            res.append(line)
        else:
            res.append(indent + line)

        while line:
            match = regex.search(line)
            if match:
                # for an even number of backslashes before the triple quote
                if len(match.group(1)) % 2 == 0:
                    if not in_quote:
                        in_quote = match.group(2)[0]
                    elif in_quote == match.group(2)[0]:
                        # if we found a matching end triple quote
                        in_quote = None
                line = line[match.end():]
            else:
                break

    return '\n'.join(res)


def _get_profiler_commands(profilers, is_server):
    prepend, append = [], []
    for profiler in profilers:
        prepend.append("job.profilers.add('%s')" % profiler.name)
        append.append("job.profilers.delete('%s')" % profiler.name)
    return prepend, append


def _sanity_check_generate_control(is_server, client_control_file, kernels):
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

    if kernels:
        # make sure that kernel is a list of dictionarions with at least
        # the 'version' key in them
        kernel_error = model_logic.ValidationError(
                {'kernel': 'The kernel parameter must be a sequence of '
                 'dictionaries containing at least the "version" key '
                 '(got: %r)' % kernels})
        try:
            iter(kernels)
        except TypeError:
            raise kernel_error
        for kernel_info in kernels:
            if (not isinstance(kernel_info, dict) or
                    'version' not in kernel_info):
                raise kernel_error


def generate_control(tests, kernels=None, platform=None, is_server=False,
                     profilers=(), client_control_file=''):
    """
    Generate a control file for a sequence of tests.

    @param tests A sequence of test control files to run.
    @param kernels A sequence of kernel info dictionaries configuring which
            kernels to boot for this job and other options for them
    @param platform A platform object with a kernel_config attribute.
    @param is_server bool, Is this a server control file rather than a client?
    @param profilers A list of profiler objects to enable during the tests.
    @param client_control_file Contents of a client control file to run as the
            last test after everything in tests.  Requires is_server=False.

    @returns The control file text as a string.
    """
    _sanity_check_generate_control(is_server=is_server, kernels=kernels,
                                   client_control_file=client_control_file)

    control_file_text = ''
    if kernels:
        control_file_text = get_kernel_stanza(kernels, platform,
                                              is_server=is_server)
    else:
        control_file_text = EMPTY_TEMPLATE

    prepend, append = _get_profiler_commands(profilers, is_server)

    control_file_text += get_tests_stanza(tests, is_server, prepend, append,
                                          client_control_file)
    return control_file_text
