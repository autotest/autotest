#!/usr/bin/env python
# coding=utf8

#  Copyright(c) 2013 Intel Corporation.
#
#  This program is free software; you can redistribute it and/or modify it
#  under the terms and conditions of the GNU General Public License,
#  version 2, as published by the Free Software Foundation.
#
#  This program is distributed in the hope it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
#  FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
#  more details.
#
#  You should have received a copy of the GNU General Public License along with
#  this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin St - Fifth Floor, Boston, MA 02110-1301 USA.
#
#  The full GNU General Public License is included in this distribution in
#  the file called "COPYING".

from optparse import OptionParser, OptionGroup
import re
import shutil
from tempfile import mktemp
import tempfile
from threading import Thread
import threading
import time
import pwd
import errno
import os
import sys
import platform
import locale
import logging
from subprocess import Popen, PIPE, CalledProcessError
import imp
from urlparse import urlunsplit
import cPickle
import cgitb

GLOBAL_CONFIG_INI = "global_config.ini"

cgitb.enable(format="text")

# prevent manually imported files from generating byte
# prevent writing *.pyc as root, e.g. common.pyc
sys.dont_write_bytecode = True

locale.setlocale(locale.LC_ALL, "en_US.UTF-8")


AT_USER = "autotest"
ATHOME_DEFAULT = '/usr/local/autotest'
AUTOTEST_DEFAULT_GIT_REPO = 'git://github.com/autotest/autotest.git'
AUTOTEST_DEFAULT_GIT_BRANCH = 'master'
DATETIMESTAMP = time.strftime("%Y-%m-%d-%H-%M-%S")
BASENAME = os.path.splitext(__file__)[0]
LOG = os.path.join(tempfile.gettempdir(), "%s-%s.log" %
                   (BASENAME, DATETIMESTAMP))
ATPASSWD = ''
MYSQLPW = ''

AUTOTESTD_SERVICE = "autotestd.service"

def setup_logging():
    # set up logging to file - see previous section for more details
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(funcName)s:%(lineno)s | %(message)s',
                        datefmt='%H:%M:%S')
                        # filename=LOG,
                        # filemode='w')
    # define a Handler which writes INFO messages or higher to the sys.stderr
    # console = logging.StreamHandler()
    # console.setLevel(logging.INFO)
    # set a format which is simpler for console use
    # formatter = logging.Formatter('%(levelname) | %(message)s')
    # tell the handler to use this format
    # console.setFormatter(formatter)
    # add the handler to the root logger
    # logging.getLogger('').addHandler(console)


def trace(func):
    """Trace entry, exit and exceptions."""
    def logged_func(*args, **kw):
        logging.info("->%s", func.__name__)
        try:
            result = func(*args, **kw)
        except:
            logging.error("exception: %s", func.__name__)
            raise
        logging.info("<-%s", func.__name__)
        return result
    logged_func.__name__ = func.__name__
    logged_func.__doc__ = func.__doc__
    return logged_func


# From autotest.client.share.base_utils
class InterruptedThread(Thread):
    """
    Run a function in a background thread.
    """
    ctx = threading.local()

    def __init__(self, target, args=None, kwargs=None):
        """
        Initialize the instance.

        @param target: Function to run in the thread.
        @param args: Arguments to pass to target.
        @param kwargs: Keyword arguments to pass to target.
        """
        Thread.__init__(self)
        self._target = target
        if args is None:
            self._args = ()
        else:
            self._args = args
        if kwargs is None:
            self._kwargs = {}
        else:
            self._kwargs = kwargs
        self._e = None
        self._retval = None

    @staticmethod
    def _exception_context(e):
        """Return the context of a given exception (or None if none is defined)."""
        return getattr(e, "_context", None)

    @classmethod
    def _get_context(cls):
        """Return the current context (or None if none is defined)."""
        if hasattr(cls.ctx, "contexts"):
            return " --> ".join([s for s in cls.ctx.contexts if s])

    @staticmethod
    def _set_exception_context(e, s):
        """Set the context of a given exception."""
        # noinspection PyAttributeOutsideInit
        e._context = s

    @staticmethod
    def _join_contexts(s1, s2):
        """Join two context strings."""
        if s1:
            if s2:
                return "%s --> %s" % (s1, s2)
            else:
                return s1
        else:
            return s2

    def run(self):
        """
        Run target (passed to the constructor).  No point in calling this
        function directly.  Call start() to make this function run in a new
        thread.
        """
        self._e = None
        self._retval = None
        try:
            try:
                self._retval = self._target(*self._args, **self._kwargs)
            except Exception:
                self._e = sys.exc_info()
                raise
        finally:
            # Avoid circular references (start() may be called only once so
            # it's OK to delete these)
            del self._target, self._args, self._kwargs

    def join(self, timeout=None, suppress_exception=False):
        """
        Join the thread.  If target raised an exception, re-raise it.
        Otherwise, return the value returned by target.

        @param timeout: Timeout value to pass to threading.Thread.join().
        @param suppress_exception: If True, don't re-raise the exception.
        """
        Thread.join(self, timeout)
        try:
            if self._e:
                if not suppress_exception:
                    # Because the exception was raised in another thread, we
                    # need to explicitly insert the current context into it
                    s = self._exception_context(self._e[1])
                    s = self._join_contexts(self._get_context(), s)
                    self._set_exception_context(self._e[1], s)
                    raise self._e[0], self._e[1], self._e[2]
            else:
                return self._retval
        finally:
            # Avoid circular references (join() may be called multiple times
            # so we can't delete these)
            self._e = None
            self._retval = None


def async_thread(func):
    def decorator(*args, **kwargs):
        t = InterruptedThread(func, args, kwargs)
        t.start()
        return t
    decorator.__name__ = func.__name__
    return decorator


def unchecked_call(cmd, loglevel=logging.debug, stdout=PIPE, stderr=PIPE, env=None, cwd=None):
    """Run cmd with arguments, redirect stderr to logging.stderr and stdout to loglevel logging function.
    Also allow for overriding stdout and stderr.
    """
    if isinstance(cmd, (str, unicode)):
        logging.debug("+ " + cmd)
        cmd = cmd.split()
    else:
        logging.debug("+ " + " ".join(cmd))
    sys.stdout.flush()
    proc = Popen(cmd, stdout=stdout, stderr=stderr, env=env, cwd=cwd)
    output, error = proc.communicate()
    if output:
        loglevel(output)
    if error:
        logging.error(error)
    sys.stdout.flush()
    return proc.returncode


def call(cmd, loglevel=logging.debug, stdout=PIPE, stderr=PIPE, env=None, cwd=None):
    """Run cmd with arguments, redirect stderr to logging.stderr and stdout to loglevel logging function.
    Also allow for overriding stdout and stderr.
    """
    if isinstance(cmd, (str, unicode)):
        logging.debug("+ " + cmd)
        cmd = cmd.split()
    else:
        logging.debug("+ " + " ".join(cmd))
    # TODO: send all command output to $LOG
    proc = Popen(cmd, stdout=stdout, stderr=stderr, env=env, cwd=cwd)
    output, error = proc.communicate()
    if output:
        loglevel(output)
    if error:
        logging.error(error)
    if proc.returncode != 0:
        raise CalledProcessError(proc.returncode, cmd)
    else:
        return 0


def wrap_cmd_with_su(cmd, user, login=True):
    """
    Wrap command with su.

    @param cmd: command to wrap
    @type cmd: str, list
    @param user: username
    @type user: str
    @param login: simulate login session, su -l
    @type login: bool
    @return: new command list
    @rtype: list
    """
    if not isinstance(cmd, basestring):
        cmd = " ".join(cmd)
    cmd_list = ["/bin/su"]
    if login:
        cmd_list.append("-l")

    # no quotes need since we are using Popen
    cmd_list.extend(["-c", cmd, user])
    return cmd_list


class AsyncCall(Popen):
    # pylint: disable=R0913
    def __init__(
            self, cmd, bufsize=0, executable=None, stdin=None, stdout=None, stderr=None, preexec_fn=None,
            close_fds=False, shell=False, cwd=None, env=None, universal_newlines=False, startupinfo=None,
            creationflags=0):
        """
        Run cmd with arguments, redirect stderr to logging.stderr and stdout to loglevel logging function.
        Also allow for overriding stdout and stderr.

        @param cmd: string or list of commands to run
        @type cmd: str, list
        @return: wrapped Popen object
        @rtype: AsyncCall
        """
        if isinstance(cmd, (str, unicode)):
            logging.debug("+ " + cmd)
            cmd = cmd.split()
        else:
            logging.debug("+ " + " ".join(cmd))
        self._saved_cmd = cmd
        self._start_time = time.time()
        super(
            AsyncCall, self).__init__(cmd, bufsize, executable, stdin, stdout, stderr, preexec_fn, close_fds, shell,
                                      cwd,
                                      env, universal_newlines, startupinfo, creationflags)

    @staticmethod
    def exit_checker(cmd, retcode, start_time):
        logging.debug(
            "duration: %.2f , cmd: %s", time.time() - start_time, cmd)
        if retcode != 0:
            raise CalledProcessError(retcode, cmd)
        else:
            return 0

    def check_exit(self):
        """
        Wait for proc to complete.  If the exit code was zero then return, otherwise raise
        CalledProcessError.  The CalledProcessError object will have the
        return code in the returncode attribute.

        @param self: existing Popen object
        @type self: AsyncCall
        @return: POSIX exit status
        @rtype: int
        """
        retcode = self.wait()
        cmd = " ".join(self._saved_cmd)
        self.exit_checker(cmd, retcode, self._start_time)


def run_as_user(username=AT_USER, cwd=None):
    def decorator(func):
        def wrapper(*args, **kwargs):
            user_pwd = pwd.getpwnam(username)
            user_uid = user_pwd.pw_uid
            user_gid = user_pwd.pw_gid
            # pylint: disable=E1101
            os.setegid(user_gid)
            os.seteuid(user_uid)
            orig_dir = os.getcwd()
            if cwd:
                os.chdir(cwd)
            try:
                logging.debug(
                    "running as user %s in %s", pwd.getpwuid(os.geteuid()).pw_name, os.getcwd())
                func(*args, **kwargs)
            finally:
                os.seteuid(os.getuid())
                os.setegid(os.getgid())
                if cwd:
                    os.chdir(orig_dir)

        return wrapper

    return decorator


def freespace(path):
    """Return the disk free space, in kibibytes
    :rtype: int
    """
    s = os.statvfs(path)
    return (s.f_bavail * s.f_bsize) / 1024


@trace
def check_disk_space():
    """
    :raises RuntimeError: when there is insufficient disk space in /usr/local or /var
    """
    local_free = freespace("/usr/local")
    var_free = freespace("/var")
    logging.info("/usr/local free %s", local_free)
    logging.info("/var free %s", var_free)
    if local_free < 5000:
        raise RuntimeError("not enough disk space in /usr/local")
    if var_free < 10000:
        raise RuntimeError("not enough disk space in /var")


@trace
def install_packages(athome):
    logging.info("Updating package dependencies")
    call([os.path.join(athome, "installation_support",
         "autotest-install-packages-deps"), "-v"], env=dict(os.environ, PYTHONPATH=athome))
    # sys.path.insert(0, athome)
    # execfile(os.path.join(athome, "installation_support", "autotest-install-
    # packages-deps"), {})


@trace
def setup_selinux():
    logging.info("Disabling SELinux (sorry guys...)")
    try:
        open("/selinux/enfore", "w").write("0\n")
    except IOError:
        pass
    call("setenforce 0")
    substitute_file("/etc/selinux/config",
                    lambda s: s.replace("SELINUX=enforcing", "SELINUX=permissive"))


def install_sub_git_repo(athome, repo, autotest_git_branch, autotest_subdir, repo_dirname):
    if os.path.isfile(os.path.join(athome, autotest_subdir, repo_dirname, ".git", "config")):
        repo_path = os.path.join(athome, autotest_subdir, repo_dirname)
        call("git remote update", cwd=repo_path)
        # do a git reset so we sync exactly with origin
        # this is for updating production servers so don't work about nuking
        # local changes
        call("git reset --hard origin/%s" % autotest_git_branch, cwd=repo_path)
    else:
        call(("git clone %s %s" %
             (repo, repo_dirname)), cwd=os.path.join(athome, autotest_subdir))


def autotest_from_git(athome, autotest_git_repo, autotest_git_branch, autotest_git_commit):
    logging.info("Cloning autotest repo %s, branch %s in %s",
                 autotest_git_repo, autotest_git_branch, athome)
    call("git init", cwd=athome)
    call("git remote add origin %s" % autotest_git_repo, cwd=athome)
    call("git fetch origin", cwd=athome)
    if autotest_git_commit:
        call(("git checkout %s" % autotest_git_commit), cwd=athome)
        call("git checkout -b specific-commit-branch", cwd=athome)
    else:
        call(("git checkout -t origin/%s" % autotest_git_branch), cwd=athome)


def backup_global_config():
    return open(GLOBAL_CONFIG_INI).read()


def install_submodules(athome, autotest_test_branch):
    logging.info(
        "Initializing and updating tests to the latest %s", autotest_test_branch)
    call("git submodule init", cwd=athome)
    call("git submodule update --recursive", cwd=athome)
    for subdir in ["client/tests", "client/tests/virt", "server/tests"]:
        call("git checkout %s" %
             autotest_test_branch, cwd=os.path.join(athome, subdir))


@trace
@run_as_user()
def install_autotest(athome, dont_update_git, autotest_git_repo,
                     autotest_git_branch, autotest_tests_branch, autotest_git_commit):
    logging.info("Installing autotest")
    if os.path.isfile(os.path.join(athome, ".git", "config")):
        if not dont_update_git:
            # backup the old global config and overwrite whatever is in git.
            # This is really crappy, we need multiple configs to allow for defaults  and local overrides.
            # TODO: merge git global config with local conifg
            global_config = backup_global_config()
            call("git reset --hard origin/%s" %
                 autotest_git_branch, cwd=athome)
            # force reset local branch name to HEAD, so local branch name
            # matches origin/autotest_git_branch
            call("git branch -f %s HEAD" % autotest_git_branch, cwd=athome)
            shutil.copy2(GLOBAL_CONFIG_INI, "git_" + GLOBAL_CONFIG_INI)
            open(GLOBAL_CONFIG_INI, "w").write(global_config)

    else:
        try:
            os.makedirs(athome)
        except OSError, e:
            if e.errno != errno.EEXIST:
                raise
        autotest_from_git(
            athome, autotest_git_repo, autotest_git_branch, autotest_git_commit)

    # workaround upstream site_tests/__init__.py
    if os.path.isfile(os.path.join(athome, "client", "site_test", "__init__.py")):
        shutil.rmtree(os.path.join(athome, "client", "site_test"))

    # Disabled, we don't use submodules
    # install_submodules(athome, autotest_tests_branch)

    git_base = os.path.dirname(autotest_git_repo)
    for autotest_subdir in ["client", "server"]:
        for repo_dirname in ["site_lib", "site_tests"]:
            install_sub_git_repo(athome, "%s/%s-%s.git" % (
                git_base, autotest_subdir, repo_dirname),
                autotest_tests_branch,
                autotest_subdir, repo_dirname)

    logging.info("Setting proper permissions for %s", athome)
    os.chmod(athome, 0755)


def get_database_module(athome):
    global _database
    try:
        return _database
    except NameError:
        module_filename = os.path.join(
            athome, "installation_support", "autotest-database-turnkey")
        _database = imp.load_source(
            "autotest_database_turnkey", module_filename)
        return _database


def wrap_args(func, sysv_args):
    def decorator(*args, **kwargs):
        old_args = sys.argv
        try:
            sys.argv = sysv_args
            return func(*args, **kwargs)
        finally:
            sys.argv = old_args
    return decorator


def run_database_turnkey(athome, sysv_args):
    mod = get_database_module(athome)
    app = mod.App()
    # insert argv[0] as module name
    return wrap_args(app.run, [mod.__name__] + sysv_args)()


@trace
def check_mysql_password(athome, mysqlpw):
    devnull = open(os.devnull, "w")
    try:
        logging.info("Setting MySQL root password")
        call("mysqladmin -u root password %s" %
             mysqlpw, stdout=devnull, stderr=devnull)
    finally:
        devnull.close()

    logging.info("Verifying MySQL root password")
    result = run_database_turnkey(athome,
                                  ["--check-credentials", "--root-password=%s" % mysqlpw])
    if result != 0:
        raise RuntimeError("MySQL already has a different root password")


@trace
def create_autotest_database(athome, mysqlpw):

    result = run_database_turnkey(athome,
                                  ["-s", "--root-password=%s" % mysqlpw, "-p", mysqlpw])
    if result != 0:
        raise RuntimeError("database something")


@trace
def build_external_packages(athome):

    filename = "build_externals.py"
    # sed -i.bak -e 's!http://google-web-
    # toolkit.googlecode.com/files/!ftp://10.55.0.98/autotest/!'
    # $ATHOME/utils/external_packages.py
    substitute_file(os.path.join(athome, "utils", "external_packages.py"),
                    lambda s: s.replace(
                        "http://google-web-toolkit.googlecode.com/files/",
                        "ftp://10.55.0.98/autotest/"))
    proc = AsyncCall(wrap_cmd_with_su(["python", os.path.join(
        athome, "utils", filename)], AT_USER))
    return proc


@trace
def build_web_rpc_client(athome):
    logging.info("Building the web rpc client (may take up to 10 minutes)")
    filename = "compile_gwt_clients.py"
    proc = AsyncCall(wrap_cmd_with_su(["python", os.path.join(
        athome, "utils", filename), "-a"], AT_USER))
    return proc


@trace
def import_tests(athome):
    logging.info("Import the base tests and profilers")
    filename = "test_importer.py"
    proc = AsyncCall(wrap_cmd_with_su(["python", os.path.join(
        athome, "utils", filename), "-A", "-v"], AT_USER))
    return proc


def make_global_config_substituter(athome):
    """
    Why?
    """
    def global_config_substituter(s):
        # replace all instances for athome.
        s = s.replace(ATHOME_DEFAULT, athome)
        #s = re.sub("autotest_top_path:.*", "autotest_top_path: %s" % athome, s)
        #s = re.sub("client_autodir_paths:.*",
        #           "client_autodir_paths: %s" % athome, s)
        #s = re.sub("test_dir:.*", "test_dir: %s" %
        #                          os.path.join(athome, "client", "site_tests"), s)
        # use new relative path name feature, site_tests will be relative to autotest_dir
        s = re.sub("test_dir:.*", "test_dir: site_tests", s)
        return s
    return global_config_substituter


def substitute_file(filename, replace_func):
    target_file = open(filename, "r+")
    try:
        contents = target_file.read()
        target_file.seek(0)
        target_file.truncate()
        contents = replace_func(contents)
        target_file.write(contents)
    finally:
        target_file.close()


@trace
def modify_global_config(athome):
    logging.info("Modifying global_config.ini")
    filename = os.path.join(athome, GLOBAL_CONFIG_INI)
    logging.info("Relocating global_config.ini entries to %s", athome)
    logging.info("Setting relative test_dir to site_tests")
    substitute_file(filename, make_global_config_substituter(athome))


@trace
def relocate_frontend_wsgi(athome):
    logging.info("Relocating frontend.wsgi to %s", athome)
    filename = os.path.join(athome, "frontend", "frontend.wsgi")
    substitute_file(filename, replace_default_athome(athome))


def setup_firewall_iptables():
    logging.info("Opening firewall for http traffic")
    iptables_path = "/etc/sysconfig/iptables"
    backup_iptables_path = "/etc/sysconfig/iptables.orig"
    f = open(iptables_path)
    try:
        iptables = f.read()
    finally:
        f.close()
    if not '--dport 80 -j ACCEPT' in iptables:
        new_iptables = re.sub(r'-A INPUT -i lo -j ACCEPT.*',
                              '\g<0>\n-A INPUT -m state --state NEW -m tcp -p tcp --dport 80 -j ACCEPT\n', iptables)
        if not os.path.isfile(backup_iptables_path):
            shutil.copy2(iptables_path, backup_iptables_path)
        f = open(iptables_path, "w")
        try:
            f.write(new_iptables)
        finally:
            f.close()
        if os.access("/etc/init.d/iptables", os.X_OK):
            call("service iptables restart")
        else:
            call("systemctl restart iptables")


@trace
def setup_firewall_firewalld(athome):
    logging.info("Opening firewall for http traffic")
    # run as root
    filename = "autotest-firewalld-add-service"
    proc = AsyncCall(["python", os.path.join(
        athome, "installation_support", filename), "-s", "http"])
    return proc.check_exit()


@trace
def setup_firewall(athome):
    if os.path.isfile("/etc/sysconfig/iptables"):
        setup_firewall_iptables()
    elif os.access("/usr/bin/firewall-cmd", os.X_OK):
        setup_firewall_firewalld(athome)


def replace_default_athome(athome):
    def replacer(s):
        return s.replace(ATHOME_DEFAULT, athome)
    return replacer


@trace
def relocate_webserver(athome):
    logging.info("Relocating apache config files to %s", athome)
    if athome != ATHOME_DEFAULT:
        substitute_file(os.path.join(
            athome, "apache/conf/afe-directives"), replace_default_athome(athome))
        substitute_file(os.path.join(
            athome, "apache/conf/django-directives"), replace_default_athome(athome))
        substitute_file(os.path.join(
            athome, "apache/conf/embedded-spreadsheet-directives"), replace_default_athome(athome))
        substitute_file(os.path.join(
            athome, "apache/conf/embedded-tko-directives"), replace_default_athome(athome))
        substitute_file(os.path.join(
            athome, "apache/conf/new-tko-directives"), replace_default_athome(athome))
        substitute_file(os.path.join(
            athome, "apache/conf/tko-directives"), replace_default_athome(athome))
        substitute_file(os.path.join(
            athome, "apache/apache-conf"), replace_default_athome(athome))
        substitute_file(os.path.join(
            athome, "apache/drone-conf"), replace_default_athome(athome))


@trace
def relocate_scheduler(athome):
    if athome != ATHOME_DEFAULT:
        logging.info(
            "Relocating scheduler scripts and service files to %s", athome)
        substitute_file(os.path.join(athome, "utils/autotest.init"),
                        lambda s: s.replace("BASE_DIR=%s" % ATHOME_DEFAULT, "BASE_DIR=%s" % athome))
        substitute_file(os.path.join(athome, "utils/autotest-rh.init"),
                        lambda s: s.replace("AUTOTEST_DIR=/usr/local/$PROG", "AUTOTEST_DIR=%s" % athome))
        substitute_file(os.path.join(athome, "utils/autotestd.service"),
                        replace_default_athome(athome))


def patch_python27_bug():
    """
    Patch some un-known python27 ctypes bug.
    """
    filename = "/usr/lib64/python2.7/ctypes/__init__.py"
    target = r"^CFUNCTYPE\(c_int\)\(lambda: None\)"
    if os.path.exists(filename):
        substitute_file(filename, lambda s: re.sub(target, r"# \g<0>", s))


def print_version_and_url(athome):
    version_module = imp.load_source("version", os.path.join(
        athome, "client/shared/version.py"))
    try:
        version = version_module.get_version()
    except ValueError, e:
        version = str(e)
    logging.info(
        "Finished installing autotest server %s at: %s", version, time.ctime())

    out = Popen(["ip", "route", "show", "to",
                 "0.0.0.0/0.0.0.0"], stdout=PIPE).communicate()[0]
    default_device = re.search(r"dev (\S+)", out).group(1)
    out = Popen(["ip", "address", "show", "dev",
                 default_device], stdout=PIPE).communicate()[0]
    local_ip = re.search(r"inet (\S+)/", out).group(1)
    print "You can access your server on %s" % urlunsplit(("http", local_ip, "afe", "", ""))


@trace
def print_install_status():
    if os.access("/etc/init.d/autotest", os.X_OK):
        call("service autotest status")
    else:
        call("systemctl status %s" % AUTOTESTD_SERVICE)


def symlink_force(src, dst):
    # atomic symlinking, symlink and then rename
    tmp_symlink = mktemp(dir=os.path.dirname(dst))
    try:
        os.symlink(src, tmp_symlink)
        os.rename(tmp_symlink, dst)
    except OSError:
        os.unlink(tmp_symlink)


try:
    # noinspection PyCompatibility
    next(iter(''), '')
except NameError:
    # noinspection PyShadowingBuiltins
    def next(*args):
        """
        Retrieve the next item from the iterator by calling its next() method.
        If default is given, it is returned if the iterator is exhausted,
        otherwise StopIteration is raised.
        New in version 2.6.

        :param iterator: the iterator
        :type iterator: iterator
        :param default: the value to return if the iterator raises StopIteration
        :type default: object
        :return: The object returned by iterator.next()
        :rtype: object
        """
        if len(args) == 2:
            try:
                return args[0].next()
            except StopIteration:
                return args[1]
        elif len(args) > 2:
            raise TypeError(
                "next expected at most 2 arguments, %s" % len(args))
        else:
            return args[0].next()


def which(program):
    """
    Search $PATH for program.

    @param program: exectuable name
    @type program: str
    @return: path of executable
    @rtype: str
    """
    paths = (os.path.join(path, program) for path in os.environ.get(
        'PATH', '').split(os.pathsep))
    matches = (os.path.realpath(p) for p in paths if os.path.exists(
        p) and os.access(p, os.X_OK))
    # noinspection PyCompatibility
    return next(matches, '')


class RHEL(object):

    @staticmethod
    @trace
    def install_basic_deps(*deps):
        missing_deps = [d for d in deps if not which(d)]
        if missing_deps:
            call("yum -d 1 -y install %s" % " ".join(missing_deps))

    @staticmethod
    def enable_service(service_name):
        if os.access(os.path.join(os.sep, "etc", "init.d", service_name), os.X_OK):
            call(("chkconfig --level 2345 %s on" % service_name))
        else:
            call("systemctl enable %s.service" % service_name)

    @staticmethod
    def restart_service(service_name):
        if os.access("/etc/init.d/%s" % service_name, os.X_OK):
            call(("service %s restart" % service_name))
        else:
            call(("systemctl restart %s.service" % service_name))

    @staticmethod
    @trace
    def setup_mysql_service():
        logging.info("Enabling MySQL server on boot")
        RHEL.enable_service("mysqld")

    @staticmethod
    @trace
    def setup_epel_repo():
        dist = platform.dist()
        if ("redhat" in dist and
           float(dist[1]) >= 6.0 and
                not os.path.isfile("/etc/yum.repos.d/epel.repo")):
            logging.info("Adding EPEL 6 repository")
            call(("rpm -ivh http://download.fedoraproject.org"
                  "/pub/epel/6/%s/epel-release-6-8.noarch.rpm" % os.uname()[4]))

    @staticmethod
    @trace
    def create_autotest_user(athome, atpasswd):
        logging.info("Creating %s user", AT_USER)
        try:
            pwd.getpwnam(AT_USER)
        except KeyError:
            logging.info("Adding user %s", AT_USER)
            call("useradd -d %s %s" % (athome, AT_USER))
            proc = Popen(["passwd", "--stdin", AT_USER], stdin=PIPE, stdout=PIPE, stderr=PIPE)
            out, err = proc.communicate(atpasswd)
            if proc.returncode != 0:
                logging.debug(out)
                logging.error(err)

    @classmethod
    @trace
    def restart_mysql(cls):
        cls.restart_service("mysqld")

    @classmethod
    @trace
    def restart_apache(cls):
        cls.restart_service("httpd")

    @classmethod
    @trace
    def configure_webserver(cls, athome):
        if not os.path.exists("/etc/httpd/conf.d/autotest/conf"):
            # if for some reason, still running with mod_python, let it be parsed before the
            # autotest config file, which has some directives to detect it
            symlink_force(os.path.join(
                athome, "apache", "conf"), "/etc/httpd/autotest.d")
            symlink_force(os.path.join(
                athome, "apache", "apache-conf"), "/etc/httpd/conf.d/z_autotest.conf")
            symlink_force(os.path.join(
                athome, "apache", "apache-web-conf"), "/etc/httpd/conf.d/z_autotest-web.conf")
        cls.enable_service("httpd")

    @classmethod
    @trace
    def start_scheduler(cls, athome):
        logging.info("Installing/starting scheduler")
        if os.path.isdir("/etc/systemd"):
            shutil.copy2(os.path.join(
                athome, "utils", AUTOTESTD_SERVICE), "/etc/systemd/system")
            call("systemctl daemon-reload")
            call(("systemctl enable %s" % AUTOTESTD_SERVICE))
            call(("systemctl stop %s" % AUTOTESTD_SERVICE))
            try:
                os.unlink(os.path.join(athome, "autotest-scheduler.pid"))
                os.unlink(os.path.join(
                    athome, "autotest-scheduler-watcher.pid"))
            except OSError, e:
                if e.errno != errno.ENOENT:
                    raise e
            call(("systemctl start %s" % AUTOTESTD_SERVICE))
        else:
            dest = "/etc/init.d/autotest"
            shutil.copy2(os.path.join(
                athome, "utils", "autotest-rh.init"), dest)
            # 0111 is chmod +x
            os.chmod(dest, os.stat(dest).st_mode | 0111)
            call("chkconfig --level 2345 autotest on")
            call("service autotest stop")
            try:
                os.unlink(os.path.join(athome, "autotest-scheduler.pid"))
                os.unlink(os.path.join(
                    athome, "autotest-scheduler-watcher.pid"))
            except OSError, e:
                if e.errno != errno.ENOENT:
                    raise e
            call("service autotest start")

    @classmethod
    def main(cls, atpasswd, mysqlpw, athome, autotest_git_repo,
             autotest_git_branch, autotest_tests_branch, autotest_git_commit,
             install_packages_only, dont_update_git):
        check_disk_space()
        cls.setup_epel_repo()
        cls.install_basic_deps("git", "passwd")
        if not install_packages_only:
            setup_selinux()
            cls.create_autotest_user(athome, atpasswd)
            install_autotest(
                athome, dont_update_git, autotest_git_repo, autotest_git_branch,
                autotest_tests_branch, autotest_git_commit)
            sys.path.insert(0, athome)
            install_packages(athome)
            build_externals_job = build_external_packages(athome)
            # build_web_rpc_client_job = build_web_rpc_client(athome)
            cls.setup_mysql_service()
            cls.restart_mysql()
            check_mysql_password(athome, mysqlpw)
            create_autotest_database(athome, mysqlpw)
            modify_global_config(athome)
            relocate_frontend_wsgi(athome)
            relocate_webserver(athome)
            cls.configure_webserver(athome)
            cls.restart_mysql()
            import_tests_job = import_tests(athome)
            patch_python27_bug()
            cls.restart_apache()
            relocate_scheduler(athome)
            import_tests_job.check_exit()
            cls.start_scheduler(athome)
            setup_firewall(athome)
            build_externals_job.check_exit()
            # build_web_rpc_client_job.check_exit()
            print_install_status()
            print_version_and_url(athome)
            print "Ignore the version.py exception"
            print "Make sure our IP is in /etc/hosts or apache might fail to start"


class Deb(object):

    @staticmethod
    def install_basic_deps(*deps):
        missing_deps = [d for d in deps if not which(d)]
        if missing_deps:
            call("apt-get install -y %s" % " ".join(missing_deps), env={
                "DEBIAN_FRONTEND": "noninteractive"})

    @staticmethod
    def setup_mysql_service():
        logging.info("Enabling MySQL server on boot")
        call("update-rc.d mysql defaults")

    @staticmethod
    def create_autotest_user(athome, atpasswd):
        logging.info("Creating %s user", AT_USER)
        try:
            pwd.getpwname(AT_USER)
        except KeyError:
            logging.info("Adding user %s", AT_USER)
            cmd = ["makepasswd", "--crypt-md5", "--clearfrom=/proc/self/fd/0"]
            proc = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
            output, error = proc.communicate(atpasswd)
            if proc.returncode != 0:
                raise CalledProcessError(proc.returncode, cmd, error)
            passwd = output.split()[1]
            call(("useradd -d %s %s -s /bin/bash -p %s" %
                 (athome, AT_USER, passwd)))

    @staticmethod
    def restart_mysql():
        call("service mysql restart")

    @staticmethod
    def restart_apache():
        call("service apache2 restart")

    @classmethod
    def configure_webserver(cls, athome):
        logging.info("Configuring Web server")
        if not os.path.exists("/etc/apache2/sites-enabled/001-autotest"):
            substitute_file(
                os.path.join(athome, "apache", "conf", "django-directives"),
                lambda s: s.replace("WSGISocketPrefix run/wsgi", "#WSGISocketPrefix run/wsgi"))
            try:
                os.unlink("/etc/apache2/sites-enabled/000-default")
            except OSError, e:
                if e.errno != errno.ENOENT:
                    raise e
            version_file = "version.load"
            version_path = os.path.join(
                "/etc/apache2/mods-available", version_file)
            if os.path.isfile(version_path):
                symlink_force(version_path,
                              os.path.join("/etc/apache2/mods-enabled", version_file))
            symlink_force(os.path.join(
                athome, "apache", "conf"), "/etc/apache2/autotest.d")
            symlink_force(os.path.join(
                athome, "apache", "apache-conf"), "/etc/apache2/sites-enabled/001-autotest")
            symlink_force(os.path.join(
                athome, "apache", "apache-web-conf"), "/etc/apache2/sites-enabled/002-autotest")
        call("a2enmod rewrite")
        call("update-rc.d apache2 defaults")

    @classmethod
    def start_scheduler(cls, athome):
        logging.info("Installing/starting scheduler")
        dest = "/etc/init.d/autotest"
        shutil.copy2(os.path.join(athome, "utils", "autotest.init"), dest)
        # 0111 is chmod +x
        os.chmod(dest, os.stat(dest).st_mode | 0111)
        call("update-rc.d autotest defaults")
        call("service autotest stop")
        try:
            os.unlink(os.path.join(athome, "autotest-scheduler.pid"))
            os.unlink(os.path.join(athome, "autotest-scheduler-watcher.pid"))
        except OSError, e:
            if e.errno != errno.ENOENT:
                raise e
        call("service autotest start")

    @classmethod
    def main(cls, atpasswd, mysqlpw, athome, autotest_git_repo,
             autotest_git_branch, autotest_tests_branch, autotest_git_commit,
             install_packages_only, dont_update_git):
        check_disk_space()
        cls.install_basic_deps("git")
        if not install_packages_only:
            cls.create_autotest_user(athome, atpasswd)
            install_autotest(
                athome, dont_update_git, autotest_git_repo, autotest_git_branch,
                autotest_tests_branch, autotest_git_commit)
            sys.path.insert(0, athome)
            install_packages(athome)
            cls.setup_mysql_service()
            cls.restart_mysql()
            check_mysql_password(athome, mysqlpw)
            create_autotest_database(athome, mysqlpw)
            build_external_packages(athome)
            modify_global_config(athome)
            relocate_frontend_wsgi(athome)
            relocate_webserver(athome)
            cls.configure_webserver(athome)
            cls.restart_mysql()
            build_web_rpc_client(athome)
            import_tests(athome)
            cls.restart_apache()
            relocate_scheduler(athome)
            cls.start_scheduler(athome)
            print_install_status()
            print_version_and_url(athome)

USAGE = """Usage: %prog

This script installs the autotest server on a given system.

Currently tested systems - Up to date versions of:

 * Fedora 16
 * Fedora 17
 * Fedora 18
 * RHEL 6.2
 * Ubuntu 12.04
 * Ubuntu 12.10

If you plan on testing your own autotest branch, make sure to set -t to a
valid upstream branch (such as master or next).

"""


def parse_args():
    # global parser, options, args
    parser = OptionParser(usage=USAGE)
    general_options_group = OptionGroup(parser, "GENERAL OPTIONS:")
    general_options_group.add_option(
        "-u", dest="atpasswd", help="Autotest user password")
    general_options_group.add_option(
        "-d", dest="mysqlpw", help="MySQL password (both mysql root and autotest_web db)")
    general_options_group.add_option(
        "-a", dest="athome", default=ATHOME_DEFAULT, help="Autotest base dir, default = %default")
    general_options_group.add_option(
        "-g", dest="autotest_git_repo",
        default=AUTOTEST_DEFAULT_GIT_REPO, help="Autotest git repo, default = %default")
    general_options_group.add_option(
        "-b", dest="autotest_git_branch",
        default=AUTOTEST_DEFAULT_GIT_BRANCH, help="Autotest git branch, default = %default")
    general_options_group.add_option(
        "-t", dest="autotest_tests_branch",
        default=AUTOTEST_DEFAULT_GIT_BRANCH, help="Autotest tests branch, default = %default")
    general_options_group.add_option(
        "-c", dest="autotest_git_commit",
        default=None, help="Autotest git commit")
    parser.add_option_group(general_options_group)
    install_step_group = OptionGroup(parser, "INSTALLATION STEP SELECTION:")
    install_step_group.add_option(
        "-p", dest="install_packages_only", action="store_true",
        default=False, help="Only install packages, default = %default")
    install_step_group.add_option(
        "-n", dest="dont_update_git", action="store_true", default=False,
        help="Do not update autotest git repo. Useful if using a modified local tree, usually when testing a modified version of this script, default = %default")
    parser.add_option_group(install_step_group)
    options, args = parser.parse_args()
    if not (options.atpasswd and options.mysqlpw):
        parser.print_help()
        sys.stdout.flush()
        raise SystemExit(1)
    return options, args


def main(options):

    start = time.time()
    os_name = platform.dist()[0]
    if os_name in set(['redhat', 'fedora']):
        current_os = RHEL
    elif os_name in set('Ubuntu'):
        current_os = Deb
    else:
        raise RuntimeError("Sorry, I can't recognize your distro, exiting...")
    current_os.main(
        options.atpasswd, options.mysqlpw, options.athome, options.autotest_git_repo, options.autotest_git_branch,
        options.autotest_tests_branch, options.autotest_git_commit, options.install_packages_only,
        options.dont_update_git)
    end = time.time()
    logging.debug("duration: %s seconds", end - start)

if __name__ == "__main__":
    setup_logging()
    parsed_options, _ = parse_args()
    logging.info("Installing the Autotest server")
    logging.info("A log of operation is kept in %s", LOG)
    logging.info("Install started at: %s", DATETIMESTAMP)
    main(parsed_options)
