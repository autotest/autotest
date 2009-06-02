import random, os, logging
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class kvmtest(test.test):
    version = 1

    def initialize(self):
        self.job.require_gcc()


    def setup(self, tarball = 'kvm-test.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.system('python setup.py install')


    def execute(self, testdir = '', args = ''):
        dirs = []
        results = []
        passed = 0
        failed = 0

        # spawn vncserver if needed
        if not os.environ.has_key('DISPLAY'):
            logging.info("No DISPLAY set in environment, spawning vncserver...")
            display = self.__create_vncserver(os.path.expanduser("~/.vnc"))
            logging.info("Setting DISPLAY=%s"%(display))
            os.environ['DISPLAY'] = display

        # build a list of dirs with 'vm.log' files
        os.path.walk(testdir, self.__has_vmlog, dirs)

        for d in dirs:
            replaydir = os.path.join(self.resultsdir, os.path.basename(d))
            os.mkdir(replaydir)
            logfile = replaydir + "/%s.log" %(os.path.basename(d))

            os.chdir(d)
            rv = utils.system("kvm-test-replay > %s" %(logfile), 1)

            results.append((d, rv))
            if rv != 0:
                screenshot = self.__get_expected_file(logfile)
                expected = "expected-%03d.png" % random.randint(0, 999)
                dest = os.path.join(replaydir,expected)

                # make a copy of the screen shot
                utils.system("cp %s %s" % (screenshot, dest), 1)

                # move the failure
                utils.system("mv failure-*.png %s" % replaydir, 1)

        # generate html output
        self.__format_results(results)

        # produce pass/fail output
        for (x, y) in results:
            if y != 0:
                logging.error("FAIL: '%s' with rv %s" % (x, y))
                failed = failed + 1
            else:
                logging.info("PASS: '%s' with rv %s" % (x, y))
                passed = passed + 1

        logging.info("Summary: Passed %d Failed %d" % (passed, failed))
        # if we had any tests not passed, fail entire test
        if failed != 0:
            raise error.TestError('kvm-test-replay')


    def __get_expected_file(self, logfile):
        # pull out screeshot name from logfile
        return filter(lambda x: "Expected" in x,
                      open(logfile, 'r').readlines())\
                      [0].split('{')[1].split('}')[0]


    def __create_vncserver(self, dirname):
        """
        this test may run without an X connection in kvm/qemu needs
        a DISPLAY to push the vga buffer.  If a DISPLAY is not set
        in the environment, then attempt to spawn a vncserver, and
        change env DISPLAY so that kvmtest can run
        """
        for pidfile in utils.locate("*:*.pid", dirname):
            pid = open(pidfile, 'r').readline().strip()
            # if the server is still active, just use it for display
            if os.path.exists('/proc/%s/status' % pid):
                vncdisplay = os.path.basename(pidfile)\
                               .split(":")[1].split(".")[0]
                logging.info("Found vncserver on port %s, using it" % vncdisplay)
                return ':%s.0' %(vncdisplay)

        # none of the vncserver were still alive, spawn our own and
        # return the display whack existing server first, then spawn it
        vncdisplay = "1"
        logging.info("Spawning vncserver on port %s" % vncdisplay)
        utils.system('vncserver :%s' % vncdisplay)
        return ':%s.0' % vncdisplay


    def __has_vmlog(self, arg, dirname, names):
        if os.path.exists(os.path.join(dirname, 'vm.log')):
            arg.append(dirname)


    def __gen_fail_html(self, testdir):
        # generate a failure index.html to display the expected and failure
        # images
        fail_dir = os.path.join(self.resultsdir, os.path.basename(testdir))
        fail_index = os.path.join(fail_dir, "index.html")

        # lambda helpers for pulling out image files
        is_png = lambda x: x.endswith('.png')
        failure_filter = lambda x: x.startswith('failure') and is_png(x)
        expected_filter = lambda x: x.startswith('expected') and is_png(x)

        failure_img = filter(failure_filter, os.listdir(fail_dir))[0]
        expected_img = filter(expected_filter, os.listdir(fail_dir))[0]
        if not failure_img or not expected_img:
            raise "Failed to find images"

        fail_buff = "<html><table border=1><tr><th>Barrier Diff</th>\n" + \
                 "<th>Expected Barrier</th><th>Failure</th></tr><tr><td></td>\n"
        for img in expected_img, failure_img:
            fail_buff = fail_buff + "<td><a href=\"%s\"><img width=320 " \
                        "height=200 src=\"%s\"></a></td>\n" % (img, img)

        fail_buff = fail_buff + "</tr></table></html>\n"

        fh = open(fail_index, "w+")
        fh.write(fail_buff)
        fh.close()

    def __format_results(self, results):
        # generate kvmtest/index.html and an index.html for each fail
        test_index = os.path.join(self.outputdir, "index.html")
        test_buff = "<html><table border=1><tr><th>Test</th>\n"

        for (x,y) in results:
            test_buff = test_buff + "<th>%s</th>\n" % os.path.basename(x)

        test_buff = test_buff + "</tr><tr><td></td>\n"

        for (x,y) in results:
            if y != 0:
                fail = "<td><a href=\"results/%s/\">FAIL</a></td>\n" % os.path.basename(x)
                test_buff = test_buff + fail
                self.__gen_fail_html(x)
            else:
                test_buff = test_buff + "<td>GOOD</td>\n"

        test_buff = test_buff + "</tr></table></html>"

        fh = open(test_index, "w+")
        fh.write(test_buff)
        fh.close()
