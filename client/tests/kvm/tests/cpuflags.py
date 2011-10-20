import logging, re, random, os, time, traceback, sys
from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.virt import kvm_monitor
from autotest_lib.client.virt import kvm_vm, virt_vm
from autotest_lib.client.virt import virt_utils, aexpect


def run_cpuflags(test, params, env):
    """
    Boot guest with different cpu flags and check if guest work correctly.
    

    @param test: kvm test objectglxge    
    
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    def subtest_fatal(f):
        """
        Decorator which mark test critical.
        If subtest failed whole test ends.
        """
        def new_f(self, *args, **kwds):
            self._fatal = True
            self.decored()
            result = f(self, *args, **kwds)
            return result
        new_f.func_name = f.func_name
        return new_f


    def subtest_nocleanup(f):
        """
        Decorator disable cleanup function.
        """
        def new_f(self, *args, **kwds):
            self._cleanup = False
            self.decored()
            result = f(self, *args, **kwds)
            return result
        new_f.func_name = f.func_name
        return new_f


    class Subtest(object):
        """
        Collect result of subtest of main test.
        """
        class DefinitionError(error.TestBaseException):
            """Indicates that method was not implemented."""
            exit_status="ERROR"

        result = []
        passed = 0
        failed = 0
        def __init__(self, *args, **kargs):
            self._fatal = False
            self._cleanup = True
            self._num_decored = 0

            ret = None
            if args is None:
                args = []
            res = [None, self.__class__.__name__, args, kargs]
            try:
                logging.info("Starting test %s" % self.__class__.__name__)
                ret = self.test(*args, **kargs)
                res[0] = True
                logging.info(Subtest.result_to_string(res))
                Subtest.result.append(res)
                Subtest.passed += 1
            except:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                for _ in range(self._num_decored):
                    exc_traceback = exc_traceback.tb_next
                logging.error("In function (" + self.__class__.__name__ + "):")
                logging.error("Call from:\n" +
                              traceback.format_stack()[-2][:-1])
                logging.error("Exception from:\n" +
                              "".join(traceback.format_exception(
                                                        exc_type, exc_value,
                                                        exc_traceback.tb_next)))
                # Clean up environment after subTest crash
                res[0] = False
                logging.info(self.result_to_string(res))
                Subtest.result.append(res)
                Subtest.failed += 1
                if self._fatal:
                    raise
            finally:
                if self._cleanup:
                    self.clean()

            return ret


        def test(self):
            """
            Check if test is defined.

            For makes test fatal add before implementation of test method
            decorator @subtest_fatal
            """
            raise Subtest.DefinitionError("Method test is not implemented.")


        def clean(self):
            """
            Check if cleanup is defined.

            For makes test fatal add before implementation of test method
            decorator @subtest_nocleanup
            """
            raise Subtest.DefinitionError("Method cleanup is not implemented.")


        def decored(self):
            self._num_decored += 1


        @classmethod
        def is_failed(cls):
            """
            @return: If any of subtest not pass return True.
            """
            if cls.failed > 0:
                return True
            else:
                return False


        @classmethod
        def get_result(cls):
            """
            @return: Result of subtests.
               Format:
                 tuple(pass/fail,function_name,call_arguments)
            """
            return cls.result


        @classmethod
        def result_to_string_debug(cls, result):
            """
            @param result: Result of test.
            """
            sargs = ""
            for arg in result[2]:
                sargs += str(arg) + ","
            sargs = sargs[:-1]
            if result[0]:
                status = "PASS"
            else:
                status = "FAIL"
            return ("Subtest (%s(%s)): --> %s") % (result[1], sargs, status)


        @classmethod
        def result_to_string(cls, result):
            """
            @param result: Result of test.
            """
            if result[0]:
                status = "PASS"
            else:
                status = "FAIL"
            return ("Subtest (%s): --> %s") % (result[1], status)


        @classmethod
        def log_append(cls, msg):
            """
            Add log_append to result output.

            @param msg: Test of log_append
            """
            cls.result.append([msg])


        @classmethod
        def _gen_res(cls, format_func):
            """
            Format result with formatting function

            @param format_func: Func for formating result.
            """
            result = ""
            for res in cls.result:
                if (len(res) == 4):
                    result += format_func(res) + "\n"
                else:
                    result += str(res[0]) + "\n"
            return result


        @classmethod
        def get_full_text_result(cls):
            """
            @return string with text form of result
            """
            return cls._gen_res(lambda s: cls.result_to_string_debug(s))


        @classmethod
        def get_text_result(cls):
            """
            @return string with text form of result
            """
            return cls._gen_res(lambda s: cls.result_to_string(s))


    class Flag(str):
        def __init__(self,  *args, **kwargs):
            super(Flag, self).__init__( *args, **kwargs) 

        def __eq__(self, other):
            s = set(self.split("|"))
            o = set(other.split("|"))
            if s & o:
                return True
            else:
                return False

        def __hash__(self, *args, **kwargs):
            return 0

    qemu_binary = virt_utils.get_path('.', params.get("qemu_binary", "qemu"))
    pwd = os.path.join(os.environ['AUTODIR'],'tests/kvm')
    stress_src = os.path.join(pwd, "scripts/cpuflags-test/cpuflags-test.tar.bz2")
    smp = int(params.get("smp", 4))

    map_flags_to_test = {
                         Flag('avx')                        :set(['avx']),
                         Flag('sse3')                       :set(['sse3']),
                         Flag('ssse3')                      :set(['ssse3']),
                         Flag('sse4.1|sse4_1|sse4.2|sse4_2'):set(['sse4']),
                         Flag('aes')                        :set(['aes','pclmul']),
                         Flag('pclmuldq')                   :set(['pclmul']),
                         Flag('pclmulqdq')                  :set(['pclmul']),
                         Flag('rdrand')                     :set(['rdrand']),
                         }

    class Hg_flags:
        def __init__(self, cpu_model):
            virtual_flags = set(map(Flag, params.get("virtual_flags", "").split()))
            self.hw_flags = set(map(Flag, params.get("hw_flags", "").split()))
            self.qemu_support_flags = get_all_qemu_flags()
            self.host_support_flags = get_host_cpuflags()
            self.quest_cpu_model_flags = get_guest_host_cpuflags(cpu_model) - \
                                         virtual_flags

            self.supported_flags = self.qemu_support_flags & \
                                   self.host_support_flags
            self.cpumodel_unsupport_flags = self.supported_flags -\
                                            self.quest_cpu_model_flags

            self.host_unsupported_flags = self.quest_cpu_model_flags - \
                                          self.host_support_flags

            self.guest_flags = self.quest_cpu_model_flags
            self.guest_flags -= self.host_unsupported_flags
            self.guest_flags |= self.cpumodel_unsupport_flags

            self.host_all_unsupported_flags = self.qemu_support_flags
            self.host_all_unsupported_flags -= self.host_support_flags | \
                                               virtual_flags


    def start_guest_with_cpuflags(cpuflags, smp=None):
        """
        Try to boot guest with special cpu flags and try login in to them.
        """
        params_b = params.copy()
        params_b["cpu_model"] = cpuflags
        if smp is not None:
            params_b["smp"] = smp

        vm_name = "vm1-cpuflags"
        vm = kvm_vm.VM(vm_name, params_b, test.bindir, env['address_cache'])
        env.register_vm(vm_name, vm)
        vm.create()
        vm.verify_alive()

        session = vm.wait_for_login()

        return (vm, session)

    def get_guest_system_cpuflags(vm_session):
        """
        Get guest system cpuflags.

        @param vm_session: session to checked vm.
        @return: [corespond flags]
        """
        flags_re = re.compile(r'^flags\s*:(.*)$',re.MULTILINE)
        out = vm_session.cmd_output("cat /proc/cpuinfo")

        flags = flags_re.search(out).groups()[0].split()
        return set(map(Flag,flags))


    def get_guest_host_cpuflags(cpumodel):
        """
        Get cpu flags correspond with cpumodel parameters.

        @param cpumodel: Cpumodel parameter sended to <qemu-kvm-cmd>.
        @return: [corespond flags]
        """
        cmd = qemu_binary + " -cpu ?dump"
        output = utils.run(cmd).stdout
        re.escape(cpumodel)
        pattern = ".+%s.*\n.*\n +feature_edx .+ \((.*)\)\n +feature_"\
                  "ecx .+ \((.*)\)\n +extfeature_edx .+ \((.*)\)\n +"\
                  "extfeature_ecx .+ \((.*)\)\n" % (cpumodel)
        flags = []
        model = re.search(pattern,output)
        if model == None:
            raise error.TestFail("Cannot find %s cpu model." % (cpumodel))
        for flag_group in model.groups():
            flags += flag_group.split()
        return set(map(Flag,flags))


    def get_all_qemu_flags():
        cmd = qemu_binary + " -cpu ?cpuid"
        output = utils.run(cmd).stdout
        
        flags_re = re.compile(r".*\n.*f_edx:(.*)\n.*f_ecx:(.*)\n.*extf_edx:"\
                              "(.*)\n.*extf_ecx:(.*)")
        m = flags_re.search(output)
        flags = []
        for a in m.groups():
            flags += a.split()

        return set(map(Flag,flags))


    def get_flags_full_name(cpu_flag):
        """
        Get all name of Flag.

        @param cpu_flag: Flag
        @return: all name of Flag.
        """
        cpu_flag = Flag(cpu_flag)
        for f in get_all_qemu_flags():
            if f == cpu_flag:
                return Flag(f)
        return []


    def get_host_cpuflags():
        """
        Get cpu flags correspond with cpumodel parameters.

        @return: [host cpu flags]
        """
        flags = virt_utils.get_cpu_flags()
        return set(map(Flag,flags))


    def parse_qemu_cpucommand(cpumodel):
        """
        Parse qemu cpu params.

        @param cpumodel: Cpu model command.
        @return: All flags which guest must have.
        """
        flags = cpumodel.split(",")
        cpumodel = flags[0]

        qemu_model_flag = get_guest_host_cpuflags(cpumodel)
        host_support_flag = get_host_cpuflags()
        real_flags = qemu_model_flag & host_support_flag

        for f in flags[1:]:
            if f[0].startswith("+"):
                real_flags |= set([get_flags_full_name(f[1:])])
            if f[0].startswith("-"):
                real_flags -= set([get_flags_full_name(f[1:])])

        return real_flags


    def get_cpu_models():
        """
        Get all cpu models from qemu.

        @return: cpu models.
        """
        cmd = qemu_binary + " -cpu ?"
        output = utils.run(cmd).stdout

        cpu_re = re.compile("\w+\s+\[?(\w+)\]?")
        return cpu_re.findall(output)


    def check_cpuflags(cpumodel, vm_session):
        """
        Check if vm flags are same like flags select by cpumodel.

        @param cpumodel: params for -cpu param in qemu-kvm
        @param vm_session: session to vm to check flags.

        @return: ([excess], [missing]) flags
        """
        gf = get_guest_system_cpuflags(vm_session)
        rf = parse_qemu_cpucommand(cpumodel)

        logging.debug("Guest flags: %s" % (gf))
        logging.debug("Host flags: %s" % (rf))
        logging.debug("Flags on guest not defined by host: %s" % (gf-rf))
        return rf-gf


    def disable_cpu(vm_session, cpu, disable=True):
        """
        Disable cpu in guest system.

        @param cpu: CPU id to disable.
        @param disable: if True disable cpu else enable cpu.
        """
        system_cpu_dir = "/sys/devices/system/cpu/"
        cpu_online = system_cpu_dir + "cpu%d/online" % (cpu)
        cpu_state = vm_session.cmd_output("cat %s" % cpu_online).strip()
        if disable and cpu_state == "1":
            vm_session.cmd("echo 0 > %s" % cpu_online)
            logging.debug("Guest cpu %d is disabled." % cpu)
        elif cpu_state == "0":
            vm_session.cmd("echo 1 > %s" % cpu_online)
            logging.debug("Guest cpu %d is enabled." % cpu)


    def install_cpuflags_test_on_vm(vm, dst_dir):
        """
        Install stress to vm.

        @param vm: virtual machine.
        @param dst_dir: Installation path.
        """
        session = vm.wait_for_login()
        vm.copy_files_to(stress_src, dst_dir)
        session.cmd("cd /tmp; tar -xvjf cpuflags-test.tar.bz2;"
                    " make EXTRA_FLAGS='';")
        session.close()


    def check_cpuflags_work(vm, path, flags):
        """
        Check which flags work.

        @param vm: Virtual machine.
        @param path: Path of cpuflags_test
        @param flags: Flags to test.
        @return: Tuple (Working, not working, not tested) flags.
        """
        pass_Flags = []
        not_tested = []
        not_working = []
        session = vm.wait_for_login()
        for f in flags:
            try:
                for tc in map_flags_to_test[f]:
                    session.cmd("%s/cpuflags-test --%s" % (path, tc))
                pass_Flags.append(f)
            except aexpect.ShellCmdError:
                not_working.append(f)
            except KeyError:
                not_tested.append(f)
        return (pass_Flags, not_working, not_tested)


    def flags_to_stresstests(flags):
        """
        Covert [cpu flags] to [tests]

        @param cpuflags: list of cpuflags
        @return: Return tests like string.
        """
        tests = set([])
        for f in flags:
            tests |= map_flags_to_test[f]
        param = ""
        for f in tests:
                param += ","+f
        return param


    def run_stress(vm, timeout, guest_flags):
        """
        Run stress on vm for timeout time.
        """
        ret = False
        install_path = "/tmp"
        install_cpuflags_test_on_vm(vm, install_path)
        Flags = check_cpuflags_work(vm, install_path, guest_flags)
        dd_session = vm.wait_for_login()
        stress_session = vm.wait_for_login()
        dd_session.sendline("dd if=/dev/[svh]da of=/tmp/stressblock"
                            " bs=10MB count=100 &")
        try:
            stress_session.cmd("%s/cpuflags-test --stress %s%s" %
                        (install_path, smp, flags_to_stresstests(Flags[0])))
        except aexpect.ShellTimeoutError:
            ret = True
        stress_session.close()
        dd_session.close()
        return ret


    def test_qemu_interface():
        """
        1) <qemu-kvm-cmd> -cpu ?model
        2) <qemu-kvm-cmd> -cpu ?dump
        3) <qemu-kvm-cmd> -cpu ?cpuid
        """

        # 1) <qemu-kvm-cmd> -cpu ?model
        class test_qemu_cpu_model(Subtest):
            @subtest_fatal
            @subtest_nocleanup
            def test(self):
                cpu_models = params.get("cpu_models","core2duo").split()
                cmd = qemu_binary + " -cpu ?model"
                result = utils.run(cmd)
                missing = []
                for cpu_model in cpu_models:
                    if not cpu_model in result.stdout:
                        missing.append(cpu_model)
                if missing:
                    raise error.TestFail("CPU models %s are not in output " 
                                         "'%s' of command \n%s" %
                                         (missing, cmd, result.stdout))

        # 2) <qemu-kvm-cmd> -cpu ?dump
        class test_qemu_dump(Subtest):
            @subtest_nocleanup
            def test(self):
                cpu_models = params.get("cpu_models","core2duo").split()
                cmd = qemu_binary + " -cpu ?dump"
                result = utils.run(cmd)
                missing = []
                for cpu_model in cpu_models:
                    if not cpu_model in result.stdout:
                        missing.append(cpu_model)
                if missing:
                    raise error.TestFail("CPU models %s are not in output "
                                         "'%s' of command \n%s" %
                                         (missing, cmd, result.stdout))

        # 3) <qemu-kvm-cmd> -cpu ?cpuid
        class test_qemu_cpuid(Subtest):
            @subtest_nocleanup
            def test(self):
                cmd = qemu_binary + " -cpu ?cpuid"
                result = utils.run(cmd)
                if result.stdout is "":
                    raise error.TestFail("There aren't any cpu Flag in output"
                                         " '%s' of command \n%s" %
                                         (cmd, result.stdout))

        test_qemu_cpu_model()
        test_qemu_dump()
        test_qemu_cpuid()


    def test_qemu_guest():
        """
        1) boot with cpu_model
        2) migrate with flags
        3) <qemu-kvm-cmd> -cpu model_name,+Flag
        4) fail boot unsupported flags
        5) check guest flags under load cpu, system (dd)
        6) online/offline CPU
        """
        cpu_models = params.get("cpu_models","").split()
        if not cpu_models:
            cpu_models = get_cpu_models()
        logging.debug("Founded cpu models %s." % (str(cpu_models)))

        # 1 boot with cpu_model
        class test_boot_cpu_model(Subtest):
            def test(self, cpu_model):
                logging.debug("Run tests with cpu model %s" % (cpu_model))
                (self.vm, session) = start_guest_with_cpuflags(cpu_model)
                not_enable_flags = check_cpuflags(cpu_model, session)
                if not_enable_flags != set([]):
                    raise error.TestFail("Flags defined by host and supported"
                                         " by host but not on find on guest: %s"
                                         % (not_enable_flags))

            def clean(self):
                logging.info("cleanup")
                self.vm.destroy(gracefully=False)

        # 2 migration test
        # TODO: Migration test.

        # 3) success boot with supported flags
        class test_boot_cpu_model_and_additiona_flags(test_boot_cpu_model):
            def test(self, cpu_model):
                flags = Hg_flags(cpu_model)

                logging.debug("Cpu mode flags %s." % str(flags.quest_cpu_model_flags))
                cpuf_model = cpu_model

                # Add unsupported flags.
                for fadd in flags.cpumodel_unsupport_flags:
                    cpuf_model += ",+" + fadd

                for fdel in flags.host_unsupported_flags:
                    cpuf_model += ",-" + fdel

                guest_flags = (flags.quest_cpu_model_flags - flags.host_unsupported_flags)
                guest_flags |= flags.cpumodel_unsupport_flags

                (self.vm, session) = start_guest_with_cpuflags(cpuf_model)

                not_enable_flags = check_cpuflags(cpuf_model, session) - \
                                   flags.hw_flags
                if not_enable_flags != set([]):
                    logging.error("Model unsupported flags: %s" %
                                  str(flags.cpumodel_unsupport_flags))
                    logging.error("Flags defined by host and supported by host but"
                                " not on find on guest: %s" % str(not_enable_flags))
                logging.info("Check main instruction sets.")

                install_path = "/tmp"
                install_cpuflags_test_on_vm(self.vm, install_path)
                Flags = check_cpuflags_work(self.vm, install_path, guest_flags)
                logging.info("Woking CPU flags: %s" % str(Flags[0]))
                logging.error("Not working CPU flags: %s" % str(Flags[1]))
                logging.warning("Not tested CPU flags: %s" % str(Flags[2]))

                if Flags[1]:
                    raise error.TestFail("Some of flags not work: %s" %
                                         (str(Flags[1])))


        # 4) fail boot unsupported flags
        class test_fail_boot_with_host_unsupported_flags(Subtest):
            @subtest_nocleanup
            def test(self, cpu_model):
                #This is virtual cpu flags which are supported by
                #qemu but no with host cpu.
                flags = Hg_flags(cpu_model)

                logging.debug("Unsupported flags %s." %
                              str(flags.host_all_unsupported_flags))
                cpuf_model = cpu_model + ",enforce"

                # Add unsupported flags.
                for fadd in flags.host_all_unsupported_flags:
                    cpuf_model += ",+" + fadd

                cmd = qemu_binary + " -cpu " + cpuf_model
                out = None
                try:
                    out = utils.run(cmd, timeout=5, ignore_status=True).stderr
                except error.CmdError:
                    logging.error("Host boot with unsupported flag")
                finally:
                    uns_re = re.compile("^warning:.*flag '(.+)'", re.MULTILINE)
                    warn_flags = set(map(Flag, uns_re.findall(out)))
                    fwarn_flags = flags.host_all_unsupported_flags - warn_flags
                    if fwarn_flags:
                        raise error.TestFail("Qemu not warn for flags %s." %
                                      str(fwarn_flags))


        # 5) check guest flags under load cpu, stress and system (dd)
        class test_boot_guest_and_try_flags_under_load(test_boot_cpu_model):
            def test(self, cpu_model):
                logging.info("***Check guest working cpuflags under load"
                             " cpu and stress and system (dd).***")

                flags = Hg_flags(cpu_model)

                logging.debug("Cpu mode flags %s." %
                              str(flags.quest_cpu_model_flags))
                logging.debug("Added flags %s." %
                              str(flags.cpumodel_unsupport_flags))
                cpuf_model = cpu_model

                # Add unsupported flags.
                for fadd in flags.cpumodel_unsupport_flags:
                    cpuf_model += ",+" + fadd

                for fdel in flags.host_unsupported_flags:
                    cpuf_model += ",-" + fdel

                (self.vm, _) = start_guest_with_cpuflags(cpuf_model, smp)

                if (not run_stress(self.vm, 60, flags.guest_flags)):
                    raise error.TestFail("Stress test ended before end of test.")


        # 6) Online/offline CPU
        class test_online_offline_guest_CPUs(test_boot_cpu_model):
            def test(self, cpu_model):
                logging.debug("Run tests with cpu model %s." % (cpu_model))
                flags = Hg_flags(cpu_model)

                (self.vm, session) = start_guest_with_cpuflags(cpu_model, smp)

                def encap(timeout):
                    random.seed()
                    begin = time.time()
                    end = begin
                    if smp > 1:
                        while end - begin < 60:
                            cpu = random.randint(1, smp - 1)
                            if random.randint(0, 1):
                                disable_cpu(session, cpu, True)
                            else:
                                disable_cpu(session, cpu, False)
                            end = time.time()
                        return True
                    else:
                        logging.warning("For this test is necessary smp > 1.")
                        return False
                timeout = 60
                result = virt_utils.parallel([(encap, [timeout]),
                                              (run_stress, [self.vm, timeout,
                                                           flags.guest_flags])])
                if not (result[0] and result[1]):
                    raise error.TestFail("Stress tests failed before"
                                         " end of testing.")


        for cpu_model in cpu_models:
            test_fail_boot_with_host_unsupported_flags(cpu_model)
            test_boot_cpu_model(cpu_model)
            test_boot_cpu_model_and_additiona_flags(cpu_model)
            test_boot_guest_and_try_flags_under_load(cpu_model)
            test_online_offline_guest_CPUs(cpu_model)


    try:
        Subtest.log_append("<qemu-kvm> interface tests.")
        test_qemu_interface()
        Subtest.log_append("<qemu-kvm> guests tests.")
        test_qemu_guest()
    finally:
        logging.info("\n\nRESULTS:\n%s \n" % (Subtest.get_text_result()))

    if Subtest.is_failed():
        raise error.TestFail("Some of subtest failed.")