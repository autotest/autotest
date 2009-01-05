# Dacapo test suite wrapper
#
import os
from autotest_lib.client.bin import utils, package, test
from autotest_lib.client.bin.test_config import config_loader
from autotest_lib.client.common_lib import error


class dacapo(test.test):
    version = 1

    def set_java_environment(self, jvm, java_root):
        '''\
        Setup java environment variables (path and classpath in order to
        execute a specific jvm specified by the java_root variable.
        java_root - Base of the java vm installation
        '''
        if jvm.startswith('ibm'):
            self.java_home = os.path.join(java_root, 'jre')
        else:
            self.java_home = java_root
        self.java_bin = os.path.join(self.java_home, 'bin')
        self.java_lib =  os.path.join(self.java_home, 'lib')
        os.environ['JAVA_ROOT'] = java_root
        os.environ['JAVA_HOME'] = self.java_home
        os.environ['JRE_HOME'] = self.java_home
        os.environ['CLASSPATH'] = self.java_lib
        os.environ['JAVA_BINDIR'] = self.java_bin
        os.environ['PATH'] = self.java_bin + ':' + os.environ['PATH']


    def execute(self, test = 'antlr', config = './dacapo.cfg', jvm = 'ibm14-ppc64'):
        # Load the test configuration. If needed, use autotest tmpdir to write
        # files.
        my_config = config_loader(config, self.tmpdir)
        # Directory where we will cache the dacapo jar file
        # and the jvm package files
        self.cachedir = os.path.join(self.bindir, 'cache')
        if not os.path.isdir(self.cachedir):
            os.makedirs(self.cachedir)

        # Get dacapo jar URL
        # (It's possible to override the default URL that points to the
        # sourceforge repository)
        if my_config.get('dacapo', 'override_default_url') == 'no':
            self.dacapo_url = my_config.get('dacapo', 'tarball_url')
        else:
            self.dacapo_url = my_config.get('dacapo', 'tarball_url_alt')
        if not self.dacapo_url:
            raise error.TestError('Could not read dacapo URL from conf file')
        # We can cache the dacapo package file if we take some
        # precautions (checking md5 sum of the downloaded file)
        self.dacapo_md5 = my_config.get('dacapo', 'package_md5')
        if not self.dacapo_md5:
            e_msg = 'Could not read dacapo package md5sum from conf file'
            raise error.TestError(e_msg)
        self.dacapo_pkg = \
        utils.unmap_url_cache(self.cachedir, self.dacapo_url,
                                       self.dacapo_md5)

        # Get jvm package URL
        self.jvm_pkg_url = my_config.get(jvm, 'jvm_pkg_url')
        if not self.jvm_pkg_url:
            raise error.TestError('Could not read java vm URL from conf file')
        # Let's cache the jvm package as well
        self.jvm_pkg_md5 = my_config.get(jvm, 'package_md5')
        if not self.jvm_pkg_md5:
            raise error.TestError('Could not read java package_md5 from conf file')
        self.jvm_pkg = \
        utils.unmap_url_cache(self.cachedir, self.jvm_pkg_url,
                                       self.jvm_pkg_md5)

        # Install the jvm pakage
        package.install(self.jvm_pkg)

        # Basic Java environment variables setup
        self.java_root = my_config.get(jvm, 'java_root')
        if not self.java_root:
            raise error.TestError('Could not read java root dir from conf file')
        self.set_java_environment(jvm, self.java_root)

        # If use_global is set to 'yes', then we want to use the global
        # setting instead of per test settings
        if my_config.get('global', 'use_global') == 'yes':
            self.iterations = my_config.get('global', 'iterations')
            self.workload = my_config.get('global', 'workload')
        else:
            self.iterations = my_config.get(test, 'iterations')
            self.workload = my_config.get(test, 'workload')

        self.verbose = '-v '
        self.workload = '-s %s ' % self.workload
        self.iterations = '-n %s ' % self.iterations
        self.scratch = '-scratch %s ' % os.path.join(self.resultsdir, test)
        # Compose the arguments string
        self.args = self.verbose + self.workload + self.scratch \
        + self.iterations + test
        # Execute the actual test
        try:
            utils.system('java -jar %s %s' % (self.dacapo_pkg, self.args))
        except:
            e_msg = \
            'Test %s has failed, command line options "%s"' % (test, self.args)
            raise error.TestError(e_msg)
