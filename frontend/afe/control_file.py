"""\
Logic for control file generation.
"""

__author__ = 'showard@google.com (Steve Howard)'

import re, os
import frontend.settings

AUTOTEST_DIR = os.path.abspath(os.path.join(
    os.path.dirname(frontend.settings.__file__), '..'))


CLIENT_KERNEL_TEMPLATE = """\
kernel = '%(kernel)s'
def step_init():
        job.next_step([step_test])
        testkernel = job.kernel('%(kernel)s')
        %(kernel_config_line)s
        testkernel.install()
        testkernel.boot(args='%(kernel_args)s')

def step_test():
"""

SERVER_KERNEL_TEMPLATE = """\
kernel = '%%(kernel)s'
kernel_install_control = \"""
%s      pass
\"""

at = autotest.Autotest()
def install_kernel(machine):
        host = hosts.SSHHost(machine)
        at.run(kernel_install_control, host=host)
job.parallel_simple(install_kernel, machines)

""" % CLIENT_KERNEL_TEMPLATE

CLIENT_STEP_TEMPLATE = "\tjob.next_step('step%d')\n"


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
    else:
        template = CLIENT_KERNEL_TEMPLATE

    stanza = template % {
        'kernel' : kernel,
        'kernel_config_line' : kernel_config_line(kernel, platform),
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
    lines = indent_text(lines, '\t')
    lines = 'def step%d():\n%s' % (item, lines)
    return lines


def get_tests_stanza(tests, is_server, prepend=[], append=[]):
    raw_control_files = [read_control_file(test) for test in tests]
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
    'Return (prepend, append)'
    prepend, append = [], []
    if is_server:
        return prepend, append
    for profiler in profilers:
        prepend.append("job.profilers.add('%s')" % profiler.name)
        append.append("job.profilers.delete('%s')" % profiler.name)
    return prepend, append


def generate_control(tests, kernel=None, platform=None, is_server=False,
                     profilers=[]):
    control_file_text = ''
    if kernel:
        control_file_text = get_kernel_stanza(kernel, platform,
                                              is_server=is_server)
    elif not is_server:
        control_file_text = 'def step_init():\n'

    prepend, append = _get_profiler_commands(profilers, is_server)

    control_file_text += get_tests_stanza(tests, is_server, prepend, append)
    return control_file_text
