import logging, time, os
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
from autotest_lib.client.tests.iozone import postprocessing
import kvm_subprocess, kvm_test_utils, kvm_utils


def run_iozone_windows(test, params, env):
    """
    Run IOzone for windows on a windows guest:
    1) Log into a guest
    2) Execute the IOzone test contained in the winutils.iso
    3) Get results
    4) Postprocess it with the IOzone postprocessing module

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    session = kvm_test_utils.wait_for_login(vm)
    results_path = os.path.join(test.resultsdir,
                                'raw_output_%s' % test.iteration)
    analysisdir = os.path.join(test.resultsdir, 'analysis_%s' % test.iteration)

    # Run IOzone and record its results
    c = command=params.get("iozone_cmd")
    t = int(params.get("iozone_timeout"))
    logging.info("Running IOzone command on guest, timeout %ss", t)
    results = session.get_command_output(command=c, timeout=t)
    utils.open_write_close(results_path, results)

    # Postprocess the results using the IOzone postprocessing module
    logging.info("Iteration succeed, postprocessing")
    a = postprocessing.IOzoneAnalyzer(list_files=[results_path],
                                      output_dir=analysisdir)
    a.analyze()
    p = postprocessing.IOzonePlotter(results_file=results_path,
                                     output_dir=analysisdir)
    p.plot_all()
