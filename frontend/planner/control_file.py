import base64
from autotest_lib.client.common_lib import utils


VERIFY_TEST_SEGMENT = """\
######################################################
### Run the verify test
######################################################

def run(machine):
    host = hosts.create_host(machine, initialize=False)
    host.log_kernel()
    ret = job.run_test('verify_test', host=host, %(verify_args)s)
    if not ret:
        raise JobError("Verify test failed; aborting job")

job.parallel_simple(run, machines)

"""

CLIENT_SEGMENT = """\
######################################################
### Run the client-side control file
######################################################

# The following is encoded in base64 in the variable control, below:
#
%(control_comment)s
#
import base64
control = base64.decodestring(%(control_base64)r)

def run(machine):
    host = hosts.create_host(machine)
    at = autotest.Autotest()
    at.run(control, host=host)

job.parallel_simple(run, machines)
"""


SERVER_SEGMENT = """\
######################################################
### Run the server side control file
######################################################

%(control_raw)s
"""

def _generate_additional_segments_dummy(**kwargs):
    return ''


def wrap_control_file(control_file, is_server, skip_verify,
                      verify_params=None, **kwargs):
    """
    Wraps a control file for use with Test Planner
    """
    wrapped = ''

    if not skip_verify:
        prepared_args = prepare_args(verify_params)
        wrapped += apply_string_arguments(VERIFY_TEST_SEGMENT,
                                          verify_args=prepared_args)

    site_generate_additional_segments = utils.import_site_function(
            __file__, 'autotest_lib.frontend.planner.site_control_file',
            'generate_additional_segments', _generate_additional_segments_dummy)
    wrapped += site_generate_additional_segments(**kwargs)

    if is_server:
        wrapped += apply_string_arguments(SERVER_SEGMENT,
                                          control_raw=control_file)
    else:
        control_base64 = base64.encodestring(control_file)
        control_comment = '\n'.join('# ' + l for l in control_file.split('\n'))
        wrapped += apply_string_arguments(CLIENT_SEGMENT,
                                          control_base64=control_base64,
                                          control_comment=control_comment)

    return wrapped


def prepare_args(args_dict):
    if not args_dict:
        return ''

    args = []
    for k, v in args_dict.iteritems():
        args.append("%s=%s" % (k, v))
    return ', '.join(args)


def apply_string_arguments(source, **kwargs):
    """
    Separate method to facilitate unit testing
    """
    return source % kwargs
