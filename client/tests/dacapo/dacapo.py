import os, re, logging, shutil
from autotest_lib.client.bin import utils, package, test
from autotest_lib.client.bin.test_config import config_loader
from autotest_lib.client.common_lib import error


class dacapo(test.test):
    """
    This autotest module runs the dacapo benchmark suite.

    This benchmark suite is intended as a tool for Java benchmarking by the
    programming language, memory management and computer architecture
    communities. It consists of a set of open source, real world applications
    with non-trivial memory loads. The suite is the culmination of over five
    years work at eight institutions, as part of the DaCapo research project,
    which was funded by a National Science Foundation ITR Grant, CCR-0085792.

    @author: Lucas Meneghel Rodrigues (lucasmr@br.ibm.com)
    @see: http://dacapobench.org/
    """
    version = 2

    def set_java_environment(self, jvm, java_root):
        """
        Setup java environment variables (path and classpath in order to
        execute a specific jvm specified by the java_root variable.
        java_root - Base of the java vm installation
        """
        if jvm.startswith('ibm'):
            java_home = os.path.join(java_root, 'jre')
        else:
            java_home = java_root
        java_bin = os.path.join(java_home, 'bin')
        java_lib =  os.path.join(java_home, 'lib')
        os.environ['JAVA_ROOT'] = java_root
        os.environ['JAVA_HOME'] = java_home
        os.environ['JRE_HOME'] = java_home
        os.environ['CLASSPATH'] = java_lib
        os.environ['JAVA_BINDIR'] = java_bin
        os.environ['PATH'] = java_bin + ':' + os.environ['PATH']


    def run_once(self, test='antlr', config='./dacapo.cfg', jvm='default'):
        cfg = config_loader(cfg=config, tmpdir=self.tmpdir, raise_errors=True)
        self.test = test
        cachedir = os.path.join(self.bindir, 'cache')
        if not os.path.isdir(cachedir):
            os.makedirs(cachedir)

        dacapo_url = cfg.get('dacapo', 'tarball_url')
        dacapo_md5 = cfg.get('dacapo', 'package_md5')
        dacapo_pkg = utils.unmap_url_cache(cachedir, dacapo_url, dacapo_md5)

        if not jvm == 'default':
            # Get the jvm package
            jvm_pkg_url = cfg.get(jvm, 'jvm_pkg_url')
            jvm_pkg_md5 = cfg.get(jvm, 'package_md5')
            jvm_pkg = utils.unmap_url_cache(cachedir, jvm_pkg_url, jvm_pkg_md5)
            # Install it
            package.install(jvm_pkg)
            # Basic Java environment variables setup
            java_root = cfg.get(jvm, 'java_root')
            self.set_java_environment(jvm, java_root)

        if cfg.get('global', 'use_global') == 'yes':
            iterations = cfg.get('global', 'iterations')
            workload = cfg.get('global', 'workload')
        else:
            iterations = cfg.get(test, 'iterations')
            workload = cfg.get(test, 'workload')

        verbose = '-v '
        workload = '-s %s ' % workload
        iterations = '-n %s ' % iterations
        self.scratch = os.path.join(self.resultsdir, test)
        scratch = '--scratch-directory %s ' % self.scratch
        args = verbose + workload + scratch + iterations + test

        self.raw_result_file = os.path.join(self.resultsdir,
                                            'raw_output_%s' % self.iteration)
        raw_result = open(self.raw_result_file, 'w')

        logging.info('Running dacapo benchmark %s', test)
        try:
            cmd = 'java -jar %s %s' % (dacapo_pkg, args)
            results = utils.run(command=cmd, stdout_tee=raw_result,
                                stderr_tee=raw_result)
            self.results = results.stderr
            raw_result.close()
        except error.CmdError, e:
            raise error.TestError('Dacapo benchmark %s has failed: %s' %
                                  (test, e))


    def postprocess_iteration(self):
        result_line = self.results.splitlines()[-1]
        time_regexp = re.compile('PASSED in (\d+) ms')
        matches = time_regexp.findall(result_line)
        if len(matches) == 1:
            keylist = {}
            logging.info('Benchmark %s completed in %s ms', self.test,
                         matches[0])
            keylist[self.test] = int(matches[0])
            self.write_perf_keyval(keylist)
            # Remove scratch directory
            shutil.rmtree(self.scratch)
        else:
            logging.error('Problems executing benchmark %s, not recording '
                          'results on the perf keyval', self.test)
