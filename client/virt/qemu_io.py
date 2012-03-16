import re, logging
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
import aexpect
import virt_utils


class QemuIOParamError(Exception):
    """
    Parameter Error for qemu-io command
    """
    pass


class QemuIO():
    """
    A class for execute qemu-io command
    """
    def __init__(self, test, params, image_name, blkdebug_cfg="",
                 prompt=r"qemu-io>\s*$", log_filename=None, io_options=""):
        self.type = ""
        if log_filename:
            log_filename += "-" + virt_utils.generate_random_string(4)
            self.output_func = virt_utils.log_line
            self.output_params = (log_filename,)
        else:
            self.output_func = None
            self.output_params = ()
        self.output_prefix = ""
        self.prompt=prompt
        self.blkdebug_cfg=blkdebug_cfg

        self.qemu_io_cmd = virt_utils.get_path(test.bindir,
                                               params.get("qemu_io_binary",
                                                          "qemu-io"))
        self.io_options = io_options
        self.run_command = False
        self.image_name = image_name
        self.blkdebug_cfg = blkdebug_cfg


    def get_cmd_line(self, ignore_option=[], essential_option=[],
                     forbid_option=[]):
        """
        Generate the command line for qemu-io from the parameters
        @params ignore_option: list for the options should not in command
        @params essential_option: list for the essential options
        @params forbid_option: list for the option should not in command
        @return: qemu-io command line
        """
        warning_flag = True
        essential_flag = False

        qemu_io_cmd = self.qemu_io_cmd
        if self.io_options:
            for io_option in re.split(",", self.io_options):
                if io_option in ignore_option:
                    pass
                elif io_option in forbid_option:
                    raise QemuIOParamError
                else:
                    if not essential_flag and io_option in essential_option:
                        essential_flag = True
                    if len(io_option) == 1:
                        qemu_io_cmd += " -%s" % io_option
                    else:
                        qemu_io_cmd += " --%s" % io_option
            if not essential_flag:
                raise QemuIOParamError

        if self.image_name:
            qemu_io_cmd += " "
            if self.blkdebug_cfg:
                qemu_io_cmd += "blkdebug:%s:" %  self.blkdebug_cfg
            qemu_io_cmd += self.image_name

        return qemu_io_cmd


    def cmd_output(self, command):
        """
        Run a command in qemu-io
        """
        pass

    def close(self):
        """
        Clean up
        """
        pass

class QemuIOShellSession(QemuIO):
    """
    Use a shell session to execute qemu-io command
    """
    def __init__(self, test, params, image_name, blkdebug_cfg="",
                 prompt=r"qemu+-io>\s*$", log_filename=None, io_options=""):
        QemuIO.__init__(self, test, params, image_name, blkdebug_cfg, prompt,
                        log_filename, io_options)

        self.type = "shell"
        forbid_option = ["h", "help", "V", "version", "c", "cmd"]
        qemu_io_cmd = self.qemu_io_cmd

        self.qemu_io_cmd = self.get_cmd_line(forbid_option=forbid_option)
        self.create_session = True
        self.session = None


    @error.context_aware
    def cmd_output(self, command, timeout=60):
        """
        Get output from shell session. If the create flag is True, init the
        shell session and set the create flag to False.
        @param command: command to execute in qemu-io
        @param timeout: timeout for execute the command
        """
        qemu_io_cmd = self.qemu_io_cmd
        prompt = self.prompt
        output_func = self.output_func
        output_params = self.output_params
        output_prefix = self.output_prefix
        if self.create_session:
            error.context("Running command: %s" % qemu_io_cmd, logging.info)
            self.session = aexpect.ShellSession(qemu_io_cmd, echo=True,
                                                prompt=prompt,
                                                output_func=output_func,
                                                output_params=output_params,
                                                output_prefix=output_prefix)
            # Record the command line in log file
            params = self.output_params + (qemu_io_cmd, )
            self.output_func(*params)

            self.create_session = False
            # Get the reaction from session
            self.session.cmd_output("\n")

        error.context("Executing command: %s" % command, logging.info)
        return self.session.cmd_output(command, timeout=timeout)


    def close(self):
        """
        Close the shell session for qemu-io
        """
        self.session.close()


class QemuIOSystem(QemuIO):
    """
    Run qemu-io with a command line which will return immediately
    """
    def __init__(self, test, params, image_name, blkdebug_cfg="",
                 prompt=r"qemu-io>\s*$", log_filename=None, io_options=""):
        QemuIO.__init__(self, test, params, image_name, blkdebug_cfg, prompt,
                        log_filename, io_options)
        ignore_option = ["c", "cmd"]
        essential_option = ["h", "help", "V", "version", "c", "cmd"]
        qemu_io_cmd = self.qemu_io_cmd

        self.qemu_io_cmd = self.get_cmd_line(ignore_option=ignore_option,
                                             essential_option=essential_option)

    @error.context_aware
    def cmd_output(self, command, timeout=60):
        """
        Get output from system_output. Add the command to the qemu-io command
        line with -c and record the output in the log file.
        @param command: command to execute in qemu-io
        @param timeout: timeout for execute the command
        """
        qemu_io_cmd = self.qemu_io_cmd
        print qemu_io_cmd
        if command:
            qemu_io_cmd += " -c '%s'" % command

        error.context("Running command: %s" % qemu_io_cmd, logging.info)
        output = utils.system_output(qemu_io_cmd, timeout=timeout)

        # Record command line in log file
        params = self.output_params + (qemu_io_cmd,)
        self.output_func(*params)

        params = self.output_params + (output,)
        self.output_func(*params)

        return output

    def close(self):
        """
        To keep the the same interface with QemuIOShellSession
        """
        pass
