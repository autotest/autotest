# dialog.py --- A python interface to the Linux "dialog" utility
# Copyright (C) 2000  Robb Shecter, Sultanbek Tezadov
# Copyright (C) 2002, 2003, 2004  Florent Rougon
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""Python interface to dialog-like programs.

This module provides a Python interface to dialog-like programs such
as `dialog', `Xdialog' and `whiptail'.

It provides a Dialog class that retains some parameters such as the
program name and path as well as the values to pass as DIALOG*
environment variables to the chosen program.

For a quick start, you should look at the demo.py file that comes
with pythondialog. It demonstrates a simple use of each widget
offered by the Dialog class.

See the Dialog class documentation for general usage information,
list of available widgets and ways to pass options to dialog.


Notable exceptions
------------------

Here is the hierarchy of notable exceptions raised by this module:

  error
     ExecutableNotFound
     BadPythonDialogUsage
     PythonDialogSystemError
        PythonDialogIOError
        PythonDialogOSError
        PythonDialogErrorBeforeExecInChildProcess
        PythonDialogReModuleError
     UnexpectedDialogOutput
     DialogTerminatedBySignal
     DialogError
     UnableToCreateTemporaryDirectory
     PythonDialogBug
     ProbablyPythonBug

As you can see, every exception `exc' among them verifies:

  issubclass(exc, error)

so if you don't need fine-grained error handling, simply catch
`error' (which will probably be accessible as dialog.error from your
program) and you should be safe.

"""

from __future__ import nested_scopes
import sys, os, tempfile, random, string, re, types


# Python < 2.3 compatibility
if sys.hexversion < 0x02030000:
    # The assignments would work with Python >= 2.3 but then, pydoc
    # shows them in the DATA section of the module...
    True = 0 == 0
    False = 0 == 1


# Exceptions raised by this module
#
# When adding, suppressing, renaming exceptions or changing their
# hierarchy, don't forget to update the module's docstring.
class error(Exception):
    """Base class for exceptions in pythondialog."""
    def __init__(self, message=None):
        self.message = message
    def __str__(self):
        return "<%s: %s>" % (self.__class__.__name__, self.message)
    def complete_message(self):
        if self.message:
            return "%s: %s" % (self.ExceptionShortDescription, self.message)
        else:
            return "%s" % self.ExceptionShortDescription
    ExceptionShortDescription = "pythondialog generic exception"

# For backward-compatibility
#
# Note: this exception was not documented (only the specific ones were), so
#       the backward-compatibility binding could be removed relatively easily.
PythonDialogException = error

class ExecutableNotFound(error):
    """Exception raised when the dialog executable can't be found."""
    ExceptionShortDescription = "Executable not found"

class PythonDialogBug(error):
    """Exception raised when pythondialog finds a bug in his own code."""
    ExceptionShortDescription = "Bug in pythondialog"

# Yeah, the "Probably" makes it look a bit ugly, but:
#   - this is more accurate
#   - this avoids a potential clash with an eventual PythonBug built-in
#     exception in the Python interpreter...
class ProbablyPythonBug(error):
    """Exception raised when pythondialog behaves in a way that seems to \
indicate a Python bug."""
    ExceptionShortDescription = "Bug in python, probably"

class BadPythonDialogUsage(error):
    """Exception raised when pythondialog is used in an incorrect way."""
    ExceptionShortDescription = "Invalid use of pythondialog"

class PythonDialogSystemError(error):
    """Exception raised when pythondialog cannot perform a "system \
operation" (e.g., a system call) that should work in "normal" situations.

    This is a convenience exception: PythonDialogIOError, PythonDialogOSError
    and PythonDialogErrorBeforeExecInChildProcess all derive from this
    exception. As a consequence, watching for PythonDialogSystemError instead
    of the aformentioned exceptions is enough if you don't need precise
    details about these kinds of errors.

    Don't confuse this exception with Python's builtin SystemError
    exception.

    """
    ExceptionShortDescription = "System error"
    
class PythonDialogIOError(PythonDialogSystemError):
    """Exception raised when pythondialog catches an IOError exception that \
should be passed to the calling program."""
    ExceptionShortDescription = "IO error"

class PythonDialogOSError(PythonDialogSystemError):
    """Exception raised when pythondialog catches an OSError exception that \
should be passed to the calling program."""
    ExceptionShortDescription = "OS error"

class PythonDialogErrorBeforeExecInChildProcess(PythonDialogSystemError):
    """Exception raised when an exception is caught in a child process \
before the exec sytem call (included).

    This can happen in uncomfortable situations like when the system is out
    of memory or when the maximum number of open file descriptors has been
    reached. This can also happen if the dialog-like program was removed
    (or if it is has been made non-executable) between the time we found it
    with _find_in_path and the time the exec system call attempted to
    execute it...

    """
    ExceptionShortDescription = "Error in a child process before the exec " \
                                "system call"

class PythonDialogReModuleError(PythonDialogSystemError):
    """Exception raised when pythondialog catches a re.error exception."""
    ExceptionShortDescription = "'re' module error"

class UnexpectedDialogOutput(error):
    """Exception raised when the dialog-like program returns something not \
expected by pythondialog."""
    ExceptionShortDescription = "Unexpected dialog output"

class DialogTerminatedBySignal(error):
    """Exception raised when the dialog-like program is terminated by a \
signal."""
    ExceptionShortDescription = "dialog-like terminated by a signal"

class DialogError(error):
    """Exception raised when the dialog-like program exits with the \
code indicating an error."""
    ExceptionShortDescription = "dialog-like terminated due to an error"

class UnableToCreateTemporaryDirectory(error):
    """Exception raised when we cannot create a temporary directory."""
    ExceptionShortDescription = "unable to create a temporary directory"

# Values accepted for checklists
try:
    _on_rec = re.compile(r"on", re.IGNORECASE)
    _off_rec = re.compile(r"off", re.IGNORECASE)

    _calendar_date_rec = re.compile(
        r"(?P<day>\d\d)/(?P<month>\d\d)/(?P<year>\d\d\d\d)$")
    _timebox_time_rec = re.compile(
        r"(?P<hour>\d\d):(?P<minute>\d\d):(?P<second>\d\d)$")
except re.error, v:
    raise PythonDialogReModuleError(v)


# This dictionary allows us to write the dialog common options in a Pythonic
# way (e.g. dialog_instance.checklist(args, ..., title="Foo", no_shadow=1)).
#
# Options such as --separate-output should obviously not be set by the user
# since they affect the parsing of dialog's output:
_common_args_syntax = {
    "aspect": lambda ratio: ("--aspect", str(ratio)),
    "backtitle": lambda backtitle: ("--backtitle", backtitle),
    "beep": lambda enable: _simple_option("--beep", enable),
    "beep_after": lambda enable: _simple_option("--beep-after", enable),
    # Warning: order = y, x!
    "begin": lambda coords: ("--begin", str(coords[0]), str(coords[1])),
    "cancel": lambda string: ("--cancel-label", string),
    "clear": lambda enable: _simple_option("--clear", enable),
    "cr_wrap": lambda enable: _simple_option("--cr-wrap", enable),
    "create_rc": lambda file: ("--create-rc", file),
    "defaultno": lambda enable: _simple_option("--defaultno", enable),
    "default_item": lambda string: ("--default-item", string),
    "help": lambda enable: _simple_option("--help", enable),
    "help_button": lambda enable: _simple_option("--help-button", enable),
    "help_label": lambda string: ("--help-label", string),
    "ignore": lambda enable: _simple_option("--ignore", enable),
    "item_help": lambda enable: _simple_option("--item-help", enable),
    "max_input": lambda size: ("--max-input", str(size)),
    "no_kill": lambda enable: _simple_option("--no-kill", enable),
    "no_cancel": lambda enable: _simple_option("--no-cancel", enable),
    "nocancel": lambda enable: _simple_option("--nocancel", enable),
    "no_shadow": lambda enable: _simple_option("--no-shadow", enable),
    "ok_label": lambda string: ("--ok-label", string),
    "print_maxsize": lambda enable: _simple_option("--print-maxsize",
                                                   enable),
    "print_size": lambda enable: _simple_option("--print-size", enable),
    "print_version": lambda enable: _simple_option("--print-version",
                                                   enable),
    "separate_output": lambda enable: _simple_option("--separate-output",
                                                     enable),
    "separate_widget": lambda string: ("--separate-widget", string),
    "shadow": lambda enable: _simple_option("--shadow", enable),
    "size_err": lambda enable: _simple_option("--size-err", enable),
    "sleep": lambda secs: ("--sleep", str(secs)),
    "stderr": lambda enable: _simple_option("--stderr", enable),
    "stdout": lambda enable: _simple_option("--stdout", enable),
    "tab_correct": lambda enable: _simple_option("--tab-correct", enable),
    "tab_len": lambda n: ("--tab-len", str(n)),
    "timeout": lambda secs: ("--timeout", str(secs)),
    "title": lambda title: ("--title", title),
    "trim": lambda enable: _simple_option("--trim", enable),
    "version": lambda enable: _simple_option("--version", enable)}
    

def _simple_option(option, enable):
    """Turn on or off the simplest dialog Common Options."""
    if enable:
        return (option,)
    else:
        # This will not add any argument to the command line
        return ()


def _find_in_path(prog_name):
    """Search an executable in the PATH.

    If PATH is not defined, the default path ":/bin:/usr/bin" is
    used.

    Return a path to the file or None if no readable and executable
    file is found.

    Notable exception: PythonDialogOSError

    """
    try:
        # Note that the leading empty component in the default value for PATH
        # could lead to the returned path not being absolute.
        PATH = os.getenv("PATH", ":/bin:/usr/bin") # see the execvp(3) man page
        for dir in string.split(PATH, ":"):
            file_path = os.path.join(dir, prog_name)
            if os.path.isfile(file_path) \
               and os.access(file_path, os.R_OK | os.X_OK):
                return file_path
        return None
    except os.error, v:
        raise PythonDialogOSError(v.strerror)


def _path_to_executable(f):
    """Find a path to an executable.

    Find a path to an executable, using the same rules as the POSIX
    exec*p functions (see execvp(3) for instance).

    If `f' contains a '/', it is assumed to be a path and is simply
    checked for read and write permissions; otherwise, it is looked
    for according to the contents of the PATH environment variable,
    which defaults to ":/bin:/usr/bin" if unset.

    The returned path is not necessarily absolute.

    Notable exceptions:

        ExecutableNotFound
        PythonDialogOSError
        
    """
    try:
        if '/' in f:
            if os.path.isfile(f) and \
                   os.access(f, os.R_OK | os.X_OK):
                res = f
            else:
                raise ExecutableNotFound("%s cannot be read and executed" % f)
        else:
            res = _find_in_path(f)
            if res is None:
                raise ExecutableNotFound(
                    "can't find the executable for the dialog-like "
                    "program")
    except os.error, v:
        raise PythonDialogOSError(v.strerror)

    return res


def _to_onoff(val):
    """Convert boolean expressions to "on" or "off"

    This function converts every non-zero integer as well as "on",
    "ON", "On" and "oN" to "on" and converts 0, "off", "OFF", etc. to
    "off".

    Notable exceptions:

        PythonDialogReModuleError
        BadPythonDialogUsage

    """
    if type(val) == types.IntType:
        if val:
            return "on"
        else:
            return "off"
    elif type(val) == types.StringType:
        try:
            if _on_rec.match(val):
                return "on"
            elif _off_rec.match(val):
                return "off"
        except re.error, v:
            raise PythonDialogReModuleError(v)
    else:
        raise BadPythonDialogUsage("invalid boolean value: %s" % val)


def _compute_common_args(dict):
    """Compute the list of arguments for dialog common options.

    Compute a list of the command-line arguments to pass to dialog
    from a keyword arguments dictionary for options listed as "common
    options" in the manual page for dialog. These are the options
    that are not tied to a particular widget.

    This allows to specify these options in a pythonic way, such as:

       d.checklist(<usual arguments for a checklist>,
                   title="...",
                   backtitle="...")

    instead of having to pass them with strings like "--title foo" or
    "--backtitle bar".

    Notable exceptions: None

    """
    args = []
    for key in dict.keys():
        args.extend(_common_args_syntax[key](dict[key]))
    return args


def _create_temporary_directory():
    """Create a temporary directory (securely).

    Return the directory path.

    Notable exceptions:
        - UnableToCreateTemporaryDirectory
        - PythonDialogOSError
        - exceptions raised by the tempfile module (which are
          unfortunately not mentioned in its documentation, at
          least in Python 2.3.3...)

    """
    find_temporary_nb_attempts = 5
    for i in range(find_temporary_nb_attempts):
        try:
            # Using something >= 2**31 causes an error in Python 2.2...
            tmp_dir = os.path.join(tempfile.gettempdir(),
                                   "%s-%u" \
                                   % ("pythondialog",
                                      random.randint(0, 2**30-1)))
        except os.error, v:
            raise PythonDialogOSError(v.strerror)

        try:
            os.mkdir(tmp_dir, 0700)
        except os.error:
            continue
        else:
            break
    else:
        raise UnableToCreateTemporaryDirectory(
            "somebody may be trying to attack us")

    return tmp_dir


# DIALOG_OK, DIALOG_CANCEL, etc. are environment variables controlling
# dialog's exit status in the corresponding situation.
#
# Note:
#    - 127 must not be used for any of the DIALOG_* values. It is used
#      when a failure occurs in the child process before it exec()s
#      dialog (where "before" includes a potential exec() failure).
#    - 126 is also used (although in presumably rare situations).
_dialog_exit_status_vars = { "OK": 0,
                             "CANCEL": 1,
                             "ESC": 2,
                             "ERROR": 3,
                             "EXTRA": 4,
                             "HELP": 5 }


# Main class of the module
class Dialog:

    """Class providing bindings for dialog-compatible programs.

    This class allows you to invoke dialog or a compatible program in
    a pythonic way to build quicky and easily simple but nice text
    interfaces.

    An application typically creates one instance of the Dialog class
    and uses it for all its widgets, but it is possible to use
    concurrently several instances of this class with different
    parameters (such as the background title) if you have the need
    for this.

    The exit code (exit status) returned by dialog is to be
    compared with the DIALOG_OK, DIALOG_CANCEL, DIALOG_ESC,
    DIALOG_ERROR, DIALOG_EXTRA and DIALOG_HELP attributes of the
    Dialog instance (they are integers).

    Note: although this class does all it can to allow the caller to
          differentiate between the various reasons that caused a
          dialog box to be closed, its backend, dialog 0.9a-20020309a
          for my tests, doesn't always return DIALOG_ESC when the
          user presses the ESC key, but often returns DIALOG_ERROR
          instead. The exit codes returned by the corresponding
          Dialog methods are of course just as wrong in these cases.
          You've been warned.


    Public methods of the Dialog class (mainly widgets)
    ---------------------------------------------------

    The Dialog class has the following methods:

    add_persistent_args
    calendar
    checklist
    fselect

    gauge_start
    gauge_update
    gauge_stop

    infobox
    inputbox
    menu
    msgbox
    passwordbox
    radiolist
    scrollbox
    tailbox
    textbox
    timebox
    yesno

    clear                 (obsolete)
    setBackgroundTitle    (obsolete)


    Passing dialog "Common Options"
    -------------------------------

    Every widget method has a **kwargs argument allowing you to pass
    dialog so-called Common Options (see the dialog(1) manual page)
    to dialog for this widget call. For instance, if `d' is a Dialog
    instance, you can write:

      d.checklist(args, ..., title="A Great Title", no_shadow=1)

    The no_shadow option is worth looking at:

      1. It is an option that takes no argument as far as dialog is
         concerned (unlike the "--title" option, for instance). When
         you list it as a keyword argument, the option is really
         passed to dialog only if the value you gave it evaluates to
         true, e.g. "no_shadow=1" will cause "--no-shadow" to be
         passed to dialog whereas "no_shadow=0" will cause this
         option not to be passed to dialog at all.

      2. It is an option that has a hyphen (-) in its name, which you
         must change into an underscore (_) to pass it as a Python
         keyword argument. Therefore, "--no-shadow" is passed by
         giving a "no_shadow=1" keyword argument to a Dialog method
         (the leading two dashes are also consistently removed).


    Exceptions
    ----------

    Please refer to the specific methods' docstrings or simply to the
    module's docstring for a list of all exceptions that might be
    raised by this class' methods.

    """

    def __init__(self, dialog="dialog", DIALOGRC=None, compat="dialog",
                 use_stdout=None):
        """Constructor for Dialog instances.

        dialog   -- name of (or path to) the dialog-like program to
                    use; if it contains a '/', it is assumed to be a
                    path and is used as is; otherwise, it is looked
                    for according to the contents of the PATH
                    environment variable, which defaults to
                    ":/bin:/usr/bin" if unset.
        DIALOGRC -- string to pass to the dialog-like program as the
                    DIALOGRC environment variable, or None if no
                    modification to the environment regarding this
                    variable should be done in the call to the
                    dialog-like program
        compat   -- compatibility mode (see below)

        The officially supported dialog-like program in pythondialog
        is the well-known dialog program written in C, based on the
        ncurses library. It is also known as cdialog and its home
        page is currently (2004-03-15) located at:

            http://dickey.his.com/dialog/dialog.html

        If you want to use a different program such as Xdialog, you
        should indicate the executable file name with the `dialog'
        argument *and* the compatibility type that you think it
        conforms to with the `compat' argument. Currently, `compat'
        can be either "dialog" (for dialog; this is the default) or
        "Xdialog" (for, well, Xdialog).

        The `compat' argument allows me to cope with minor
        differences in behaviour between the various programs
        implementing the dialog interface (not the text or graphical
        interface, I mean the "API"). However, having to support
        various APIs simultaneously is a bit ugly and I would really
        prefer you to report bugs to the relevant maintainers when
        you find incompatibilities with dialog. This is for the
        benefit of pretty much everyone that relies on the dialog
        interface.

        Notable exceptions:

            ExecutableNotFound
            PythonDialogOSError

        """        
        # DIALOGRC differs from the other DIALOG* variables in that:
        #   1. It should be a string if not None
        #   2. We may very well want it to be unset
        if DIALOGRC is not None:
            self.DIALOGRC = DIALOGRC

        # After reflexion, I think DIALOG_OK, DIALOG_CANCEL, etc.
        # should never have been instance attributes (I cannot see a
        # reason why the user would want to change their values or
        # even read them), but it is a bit late, now. So, we set them
        # based on the (global) _dialog_exit_status_vars.keys.
        for var in _dialog_exit_status_vars.keys():
            varname = "DIALOG_" + var
            setattr(self, varname, _dialog_exit_status_vars[var])

        self._dialog_prg = _path_to_executable(dialog)
        self.compat = compat
        self.dialog_persistent_arglist = []

        # Use stderr or stdout?
        if self.compat == "Xdialog":
            # Default to stdout if Xdialog
            self.use_stdout = True
        else:
            self.use_stdout = False
        if use_stdout != None:
            # Allow explicit setting
            self.use_stdout = use_stdout
        if self.use_stdout:
            self.add_persistent_args(["--stdout"])

    def add_persistent_args(self, arglist):
        self.dialog_persistent_arglist.extend(arglist)

    # For compatibility with the old dialog...
    def setBackgroundTitle(self, text):
        """Set the background title for dialog.

        This method is obsolete. Please remove calls to it from your
        programs.

	"""
	self.add_persistent_args(("--backtitle", text))

    def _call_program(self, redirect_child_stdin, cmdargs, **kwargs):
	"""Do the actual work of invoking the dialog-like program.

        Communication with the dialog-like program is performed
        through one or two pipes, depending on
        `redirect_child_stdin'. There is always one pipe that is
        created to allow the parent process to read what dialog
        writes on its standard error stream.
        
        If `redirect_child_stdin' is True, an additional pipe is
        created whose reading end is connected to dialog's standard
        input. This is used by the gauge widget to feed data to
        dialog.

        Beware when interpreting the return value: the length of the
        returned tuple depends on `redirect_child_stdin'.

        Notable exception: PythonDialogOSError (if pipe() or close()
                           system calls fail...)

        """
        # We want to define DIALOG_OK, DIALOG_CANCEL, etc. in the
        # environment of the child process so that we know (and
        # even control) the possible dialog exit statuses.
        new_environ = {}
        new_environ.update(os.environ)
        for var in _dialog_exit_status_vars:
            varname = "DIALOG_" + var
            new_environ[varname] = str(getattr(self, varname))
        if hasattr(self, "DIALOGRC"):
            new_environ["DIALOGRC"] = self.DIALOGRC

        # Create:
        #   - a pipe so that the parent process can read dialog's output on
        #     stdout/stderr
        #   - a pipe so that the parent process can feed data to dialog's
        #     stdin (this is needed for the gauge widget) if
        #     redirect_child_stdin is True
        try:
            # rfd = File Descriptor for Reading
            # wfd = File Descriptor for Writing
            (child_rfd, child_wfd) = os.pipe()
            if redirect_child_stdin:
                (child_stdin_rfd,  child_stdin_wfd)  = os.pipe()
        except os.error, v:
            raise PythonDialogOSError(v.strerror)

        child_pid = os.fork()
        if child_pid == 0:
            # We are in the child process. We MUST NOT raise any exception.
            try:
                # The child process doesn't need these file descriptors
                os.close(child_rfd)
                if redirect_child_stdin:
                    os.close(child_stdin_wfd)
                # We want:
                #   - dialog's output on stderr/stdout to go to child_wfd
                #   - data written to child_stdin_wfd to go to dialog's stdin
                #     if redirect_child_stdin is True
                if self.use_stdout:
                    os.dup2(child_wfd, 1)
                else:
                    os.dup2(child_wfd, 2)
                if redirect_child_stdin:
                    os.dup2(child_stdin_rfd, 0)

                arglist = [self._dialog_prg] + \
                          self.dialog_persistent_arglist + \
                          _compute_common_args(kwargs) + \
                          cmdargs
                # Insert here the contents of the DEBUGGING file if you want
                # to obtain a handy string of the complete command line with
                # arguments quoted for the shell and environment variables
                # set.
                os.execve(self._dialog_prg, arglist, new_environ)
            except:
                os._exit(127)

            # Should not happen unless there is a bug in Python
            os._exit(126)

        # We are in the father process.
        #
        # It is essential to close child_wfd, otherwise we will never
        # see EOF while reading on child_rfd and the parent process
        # will block forever on the read() call.
        # [ after the fork(), the "reference count" of child_wfd from
        #   the operating system's point of view is 2; after the child exits,
        #   it is 1 until the father closes it itself; then it is 0 and a read
        #   on child_rfd encounters EOF once all the remaining data in
        #   the pipe has been read. ]
        try:
            os.close(child_wfd)
            if redirect_child_stdin:
                os.close(child_stdin_rfd)
                return (child_pid, child_rfd, child_stdin_wfd)
            else:
                return (child_pid, child_rfd)
        except os.error, v:
            raise PythonDialogOSError(v.strerror)

    def _wait_for_program_termination(self, child_pid, child_rfd):
        """Wait for a dialog-like process to terminate.

        This function waits for the specified process to terminate,
        raises the appropriate exceptions in case of abnormal
        termination and returns the exit status and standard error
        output of the process as a tuple: (exit_code, stderr_string).

        `child_rfd' must be the file descriptor for the
        reading end of the pipe created by self._call_program()
        whose writing end was connected by self._call_program() to
        the child process's standard error.

        This function reads the process's output on standard error
        from `child_rfd' and closes this file descriptor once
        this is done.

        Notable exceptions:

            DialogTerminatedBySignal
            DialogError
            PythonDialogErrorBeforeExecInChildProcess
            PythonDialogIOError
            PythonDialogBug
            ProbablyPythonBug

        """
        exit_info = os.waitpid(child_pid, 0)[1]
        if os.WIFEXITED(exit_info):
            exit_code = os.WEXITSTATUS(exit_info)
        # As we wait()ed for the child process to terminate, there is no
        # need to call os.WIFSTOPPED()
        elif os.WIFSIGNALED(exit_info):
            raise DialogTerminatedBySignal("the dialog-like program was "
                                           "terminated by signal %u" %
                                           os.WTERMSIG(exit_info))
        else:
            raise PythonDialogBug("please report this bug to the "
                                  "pythondialog maintainers")

        if exit_code == self.DIALOG_ERROR:
            raise DialogError("the dialog-like program exited with "
                              "code %d (was passed to it as the DIALOG_ERROR "
                              "environment variable)" % exit_code)
        elif exit_code == 127:
            raise PythonDialogErrorBeforeExecInChildProcess(
                "perhaps the dialog-like program could not be executed; "
                "perhaps the system is out of memory; perhaps the maximum "
                "number of open file descriptors has been reached")
        elif exit_code == 126:
            raise ProbablyPythonBug(
                "a child process returned with exit status 126; this might "
                "be the exit status of the dialog-like program, for some "
                "unknown reason (-> probably a bug in the dialog-like "
                "program); otherwise, we have probably found a python bug")
        
        # We might want to check here whether exit_code is really one of
        # DIALOG_OK, DIALOG_CANCEL, etc. However, I prefer not doing it
        # because it would break pythondialog for no strong reason when new
        # exit codes are added to the dialog-like program.
        #
        # As it is now, if such a thing happens, the program using
        # pythondialog may receive an exit_code it doesn't know about. OK, the
        # programmer just has to tell the pythondialog maintainer about it and
        # can temporarily set the appropriate DIALOG_* environment variable if
        # he wants and assign the corresponding value to the Dialog instance's
        # DIALOG_FOO attribute from his program. He doesn't even need to use a
        # patched pythondialog before he upgrades to a version that knows
        # about the new exit codes.
        #
        # The bad thing that might happen is a new DIALOG_FOO exit code being
        # the same by default as one of those we chose for the other exit
        # codes already known by pythondialog. But in this situation, the
        # check that is being discussed wouldn't help at all.

        # Read dialog's output on its stderr
        try:
            child_output = os.fdopen(child_rfd, "rb").read()
            # Now, since the file object has no reference anymore, the
            # standard IO stream behind it will be closed, causing the
            # end of the the pipe we used to read dialog's output on its
            # stderr to be closed (this is important, otherwise invoking
            # dialog enough times will eventually exhaust the maximum number
            # of open file descriptors).
        except IOError, v:
            raise PythonDialogIOError(v)

        return (exit_code, child_output)

    def _perform(self, cmdargs, **kwargs):
	"""Perform a complete dialog-like program invocation.

        This function invokes the dialog-like program, waits for its
        termination and returns its exit status and whatever it wrote
        on its standard error stream.

        Notable exceptions:

            any exception raised by self._call_program() or
            self._wait_for_program_termination()

        """
        (child_pid, child_rfd) = \
                    self._call_program(False, *(cmdargs,), **kwargs)
        (exit_code, output) = \
                    self._wait_for_program_termination(child_pid,
                                                        child_rfd)
	return (exit_code, output)

    def _strip_xdialog_newline(self, output):
        """Remove trailing newline (if any), if using Xdialog"""
        if self.compat == "Xdialog" and output.endswith("\n"):
            output = output[:-1]
        return output

    # This is for compatibility with the old dialog.py
    def _perform_no_options(self, cmd):
	"""Call dialog without passing any more options."""
	return os.system(self._dialog_prg + ' ' + cmd)

    # For compatibility with the old dialog.py
    def clear(self):
	"""Clear the screen. Equivalent to the dialog --clear option.

        This method is obsolete. Please remove calls to it from your
        programs.

	"""
	self._perform_no_options('--clear')

    def calendar(self, text, height=6, width=0, day=0, month=0, year=0,
                 **kwargs):
        """Display a calendar dialog box.

        text   -- text to display in the box
        height -- height of the box (minus the calendar height)
        width  -- width of the box
        day    -- inititial day highlighted
        month  -- inititial month displayed
        year   -- inititial year selected (0 causes the current date
                  to be used as the initial date)
        
        A calendar box displays month, day and year in separately
        adjustable windows. If the values for day, month or year are
        missing or negative, the current date's corresponding values
        are used. You can increment or decrement any of those using
        the left, up, right and down arrows. Use tab or backtab to
        move between windows. If the year is given as zero, the
        current date is used as an initial value.

        Return a tuple of the form (code, date) where `code' is the
        exit status (an integer) of the dialog-like program and
        `date' is a list of the form [day, month, year] (where `day',
        `month' and `year' are integers corresponding to the date
        chosen by the user) if the box was closed with OK, or None if
        it was closed with the Cancel button.

        Notable exceptions:
            - any exception raised by self._perform()
            - UnexpectedDialogOutput
            - PythonDialogReModuleError

	"""
	(code, output) = self._perform(
            *(["--calendar", text, str(height), str(width), str(day),
               str(month), str(year)],),
            **kwargs)
        if code == self.DIALOG_OK:
            try:
                mo = _calendar_date_rec.match(output)
            except re.error, v:
                raise PythonDialogReModuleError(v)
            
            if mo is None:
                raise UnexpectedDialogOutput(
                    "the dialog-like program returned the following "
                    "unexpected date with the calendar box: %s" % output)
            date = map(int, mo.group("day", "month", "year"))
        else:
            date = None
        return (code, date)

    def checklist(self, text, height=15, width=54, list_height=7,
                  choices=[], **kwargs):
	"""Display a checklist box.

        text        -- text to display in the box
        height      -- height of the box
        width       -- width of the box
        list_height -- number of entries displayed in the box (which
                       can be scrolled) at a given time
        choices     -- a list of tuples (tag, item, status) where
                       `status' specifies the initial on/off state of
                       each entry; can be 0 or 1 (integers, 1 meaning
                       checked, i.e. "on"), or "on", "off" or any
                       uppercase variant of these two strings.

        Return a tuple of the form (code, [tag, ...]) with the tags
        for the entries that were selected by the user. `code' is the
        exit status of the dialog-like program.

        If the user exits with ESC or CANCEL, the returned tag list
        is empty.

        Notable exceptions:

            any exception raised by self._perform() or _to_onoff()

        """
        cmd = ["--checklist", text, str(height), str(width), str(list_height)]
        for t in choices:
            cmd.extend(((t[0], t[1], _to_onoff(t[2]))))

        # The dialog output cannot be parsed reliably (at least in dialog
        # 0.9b-20040301) without --separate-output (because double quotes in
        # tags are escaped with backslashes, but backslashes are not
        # themselves escaped and you have a problem when a tag ends with a
        # backslash--the output makes you think you've encountered an embedded
        # double-quote).
        kwargs["separate_output"] = True

	(code, output) = self._perform(*(cmd,), **kwargs)

        # Since we used --separate-output, the tags are separated by a newline
        # in the output. There is also a final newline after the last tag.
        if output:
            return (code, string.split(output, '\n')[:-1])
        else:                           # empty selection
            return (code, [])

    def fselect(self, filepath, height, width, **kwargs):
        """Display a file selection dialog box.

        filepath -- initial file path
        height   -- height of the box
        width    -- width of the box
        
        The file-selection dialog displays a text-entry window in
        which you can type a filename (or directory), and above that
        two windows with directory names and filenames.

        Here, filepath can be a file path in which case the file and
        directory windows will display the contents of the path and
        the text-entry window will contain the preselected filename.

        Use tab or arrow keys to move between the windows. Within the
        directory or filename windows, use the up/down arrow keys to
        scroll the current selection. Use the space-bar to copy the
        current selection into the text-entry window.

        Typing any printable character switches focus to the
        text-entry window, entering that character as well as
        scrolling the directory and filename windows to the closest
        match.

        Use a carriage return or the "OK" button to accept the
        current value in the text-entry window, or the "Cancel"
        button to cancel.

        Return a tuple of the form (code, path) where `code' is the
        exit status (an integer) of the dialog-like program and
        `path' is the path chosen by the user (whose last element may
        be a directory or a file).
              
        Notable exceptions:

            any exception raised by self._perform()

	"""
        (code, output) = self._perform(
            *(["--fselect", filepath, str(height), str(width)],),
            **kwargs)

        output = self._strip_xdialog_newline(output)
        
	return (code, output)
    
    def gauge_start(self, text="", height=8, width=54, percent=0, **kwargs):
	"""Display gauge box.

        text    -- text to display in the box
        height  -- height of the box
        width   -- width of the box
        percent -- initial percentage shown in the meter

        A gauge box displays a meter along the bottom of the box. The
        meter indicates a percentage.

        This function starts the dialog-like program telling it to
        display a gauge box with a text in it and an initial
        percentage in the meter.

        Return value: undefined.


        Gauge typical usage
        -------------------

        Gauge typical usage (assuming that `d' is an instance of the
	Dialog class) looks like this:
	    d.gauge_start()
	    # do something
	    d.gauge_update(10)       # 10% of the whole task is done
	    # ...
	    d.gauge_update(100, "any text here") # work is done
	    exit_code = d.gauge_stop()           # cleanup actions


        Notable exceptions:
            - any exception raised by self._call_program()
            - PythonDialogOSError

	"""
        (child_pid, child_rfd, child_stdin_wfd) = self._call_program(
            True,
            *(["--gauge", text, str(height), str(width), str(percent)],),
            **kwargs)
        try:
            self._gauge_process = {
                "pid": child_pid,
                "stdin": os.fdopen(child_stdin_wfd, "wb"),
                "child_rfd": child_rfd
                }
        except os.error, v:
            raise PythonDialogOSError(v.strerror)
            
    def gauge_update(self, percent, text="", update_text=0):
	"""Update a running gauge box.
	
        percent     -- new percentage to show in the gauge meter
        text        -- new text to optionally display in the box
        update-text -- boolean indicating whether to update the
                       text in the box

        This function updates the percentage shown by the meter of a
        running gauge box (meaning `gauge_start' must have been
        called previously). If update_text is true (for instance, 1),
        the text displayed in the box is also updated.

	See the `gauge_start' function's documentation for
	information about how to use a gauge.

        Return value: undefined.

        Notable exception: PythonDialogIOError can be raised if there
                           is an I/O error while writing to the pipe
                           used to talk to the dialog-like program.

	"""
	if update_text:
	    gauge_data = "%d\nXXX\n%s\nXXX\n" % (percent, text)
	else:
	    gauge_data = "%d\n" % percent
	try:
            self._gauge_process["stdin"].write(gauge_data)
            self._gauge_process["stdin"].flush()
        except IOError, v:
            raise PythonDialogIOError(v)
    
    # For "compatibility" with the old dialog.py...
    gauge_iterate = gauge_update

    def gauge_stop(self):
	"""Terminate a running gauge.

        This function performs the appropriate cleanup actions to
        terminate a running gauge (started with `gauge_start').
	
	See the `gauge_start' function's documentation for
	information about how to use a gauge.

        Return value: undefined.

        Notable exceptions:
            - any exception raised by
              self._wait_for_program_termination()
            - PythonDialogIOError can be raised if closing the pipe
              used to talk to the dialog-like program fails.

	"""
        p = self._gauge_process
        # Close the pipe that we are using to feed dialog's stdin
        try:
            p["stdin"].close()
        except IOError, v:
            raise PythonDialogIOError(v)
        exit_code = \
                  self._wait_for_program_termination(p["pid"],
                                                      p["child_rfd"])[0]
        return exit_code

    def infobox(self, text, height=10, width=30, **kwargs):
        """Display an information dialog box.

        text   -- text to display in the box
        height -- height of the box
        width  -- width of the box

        An info box is basically a message box. However, in this
        case, dialog will exit immediately after displaying the
        message to the user. The screen is not cleared when dialog
        exits, so that the message will remain on the screen until
        the calling shell script clears it later. This is useful
        when you want to inform the user that some operations are
        carrying on that may require some time to finish.

        Return the exit status (an integer) of the dialog-like
        program.

        Notable exceptions:

            any exception raised by self._perform()

	"""
	return self._perform(
            *(["--infobox", text, str(height), str(width)],),
            **kwargs)[0]

    def inputbox(self, text, height=10, width=30, init='', **kwargs):
        """Display an input dialog box.

        text   -- text to display in the box
        height -- height of the box
        width  -- width of the box
        init   -- default input string

        An input box is useful when you want to ask questions that
        require the user to input a string as the answer. If init is
        supplied it is used to initialize the input string. When
        entering the string, the BACKSPACE key can be used to
        correct typing errors. If the input string is longer than
        can fit in the dialog box, the input field will be scrolled.

        Return a tuple of the form (code, string) where `code' is the
        exit status of the dialog-like program and `string' is the
        string entered by the user.

        Notable exceptions:

            any exception raised by self._perform()

	"""
        (code, tag) = self._perform(
            *(["--inputbox", text, str(height), str(width), init],),
            **kwargs)

        tag = self._strip_xdialog_newline(tag)
        
	return (code, tag)

    def menu(self, text, height=15, width=54, menu_height=7, choices=[],
             **kwargs):
        """Display a menu dialog box.

        text        -- text to display in the box
        height      -- height of the box
        width       -- width of the box
        menu_height -- number of entries displayed in the box (which
                       can be scrolled) at a given time
        choices     -- a sequence of (tag, item) or (tag, item, help)
                       tuples (the meaning of each `tag', `item' and
                       `help' is explained below)


        Overview
        --------

        As its name suggests, a menu box is a dialog box that can be
        used to present a list of choices in the form of a menu for
        the user to choose. Choices are displayed in the order given.

        Each menu entry consists of a `tag' string and an `item'
        string. The tag gives the entry a name to distinguish it from
        the other entries in the menu. The item is a short
        description of the option that the entry represents.

        The user can move between the menu entries by pressing the
        UP/DOWN keys, the first letter of the tag as a hot-key, or
        the number keys 1-9. There are menu-height entries displayed
        in the menu at one time, but the menu will be scrolled if
        there are more entries than that.


        Providing on-line help facilities
        ---------------------------------

        If this function is called with item_help=1 (keyword
        argument), the option --item-help is passed to dialog and the
        tuples contained in `choices' must contain 3 elements each :
        (tag, item, help). The help string for the highlighted item
        is displayed in the bottom line of the screen and updated as
        the user highlights other items.

        If item_help=0 or if this keyword argument is not passed to
        this function, the tuples contained in `choices' must contain
        2 elements each : (tag, item).

        If this function is called with help_button=1, it must also
        be called with item_help=1 (this is a limitation of dialog),
        therefore the tuples contained in `choices' must contain 3
        elements each as explained in the previous paragraphs. This
        will cause a Help button to be added to the right of the
        Cancel button (by passing --help-button to dialog).


        Return value
        ------------

        Return a tuple of the form (exit_info, string).

        `exit_info' is either:
          - an integer, being the the exit status of the dialog-like
            program
          - or the string "help", meaning that help_button=1 was
            passed and that the user chose the Help button instead of
            OK or Cancel.

        The meaning of `string' depends on the value of exit_info:
          - if `exit_info' is 0, `string' is the tag chosen by the
            user
          - if `exit_info' is "help", `string' is the `help' string
            from the `choices' argument corresponding to the item
            that was highlighted when the user chose the Help button
          - otherwise (the user chose Cancel or pressed Esc, or there
            was a dialog error), the value of `string' is undefined.

        Notable exceptions:

            any exception raised by self._perform()

	"""
        cmd = ["--menu", text, str(height), str(width), str(menu_height)]
        for t in choices:
            cmd.extend(t)
	(code, output) = self._perform(*(cmd,), **kwargs)

        output = self._strip_xdialog_newline(output)
        
        if "help_button" in kwargs.keys() and output.startswith("HELP "):
            return ("help", output[5:])
        else:
            return (code, output)

    def msgbox(self, text, height=10, width=30, **kwargs):
        """Display a message dialog box.

        text   -- text to display in the box
        height -- height of the box
        width  -- width of the box

        A message box is very similar to a yes/no box. The only
        difference between a message box and a yes/no box is that a
        message box has only a single OK button. You can use this
        dialog box to display any message you like. After reading
        the message, the user can press the ENTER key so that dialog
        will exit and the calling program can continue its
        operation.

        Return the exit status (an integer) of the dialog-like
        program.

        Notable exceptions:

            any exception raised by self._perform()

	"""
	return self._perform(
            *(["--msgbox", text, str(height), str(width)],),
            **kwargs)[0]

    def passwordbox(self, text, height=10, width=60, init='', **kwargs):
        """Display an password input dialog box.

        text   -- text to display in the box
        height -- height of the box
        width  -- width of the box
        init   -- default input password

        A password box is similar to an input box, except that the
        text the user enters is not displayed. This is useful when
        prompting for passwords or other sensitive information. Be
        aware that if anything is passed in "init", it will be
        visible in the system's process table to casual snoopers.
        Also, it is very confusing to the user to provide them with a
        default password they cannot see. For these reasons, using
        "init" is highly discouraged.

        Return a tuple of the form (code, password) where `code' is
        the exit status of the dialog-like program and `password' is
        the password entered by the user.

        Notable exceptions:

            any exception raised by self._perform()

	"""
	(code, password) = self._perform(
            *(["--passwordbox", text, str(height), str(width), init],),
            **kwargs)

        password = self._strip_xdialog_newline(password)

        return (code, password)

    def radiolist(self, text, height=15, width=54, list_height=7,
                  choices=[], **kwargs):
	"""Display a radiolist box.

        text        -- text to display in the box
        height      -- height of the box
        width       -- width of the box
        list_height -- number of entries displayed in the box (which
                       can be scrolled) at a given time
        choices     -- a list of tuples (tag, item, status) where
                       `status' specifies the initial on/off state
                       each entry; can be 0 or 1 (integers, 1 meaning
                       checked, i.e. "on"), or "on", "off" or any
                       uppercase variant of these two strings.
                       No more than one entry should  be set to on.

        A radiolist box is similar to a menu box. The main difference
        is that you can indicate which entry is initially selected,
        by setting its status to on.

        Return a tuple of the form (code, tag) with the tag for the
        entry that was chosen by the user. `code' is the exit status
        of the dialog-like program.

        If the user exits with ESC or CANCEL, or if all entries were
        initially set to off and not altered before the user chose
        OK, the returned tag is the empty string.

        Notable exceptions:

            any exception raised by self._perform() or _to_onoff()

	"""
        cmd = ["--radiolist", text, str(height), str(width), str(list_height)]
        for t in choices:
            cmd.extend(((t[0], t[1], _to_onoff(t[2]))))

        (code, tag) = self._perform(*(cmd,), **kwargs)

        tag = self._strip_xdialog_newline(tag)
            
	return (code, tag)

    def scrollbox(self, text, height=20, width=78, **kwargs):
	"""Display a string in a scrollable box.

        text   -- text to display in the box
        height -- height of the box
        width  -- width of the box

        This method is a layer on top of textbox. The textbox option
        in dialog allows to display file contents only. This method
        allows you to display any text in a scrollable box. This is
        simply done by creating a temporary file, calling textbox and
        deleting the temporary file afterwards.

        Return the dialog-like program's exit status.

        Notable exceptions:
            - UnableToCreateTemporaryDirectory
            - PythonDialogIOError
            - PythonDialogOSError
            - exceptions raised by the tempfile module (which are
              unfortunately not mentioned in its documentation, at
              least in Python 2.3.3...)

	"""
        # In Python < 2.3, the standard library does not have
        # tempfile.mkstemp(), and unfortunately, tempfile.mktemp() is
        # insecure. So, I create a non-world-writable temporary directory and
        # store the temporary file in this directory.
        try:
            # We want to ensure that f is already bound in the local
            # scope when the finally clause (see below) is executed
            f = 0
            tmp_dir = _create_temporary_directory()
            # If we are here, tmp_dir *is* created (no exception was raised),
            # so chances are great that os.rmdir(tmp_dir) will succeed (as
            # long as tmp_dir is empty).
            #
            # Don't move the _create_temporary_directory() call inside the
            # following try statement, otherwise the user will always see a
            # PythonDialogOSError instead of an
            # UnableToCreateTemporaryDirectory because whenever
            # UnableToCreateTemporaryDirectory is raised, the subsequent
            # os.rmdir(tmp_dir) is bound to fail.
            try:
                fName = os.path.join(tmp_dir, "text")
                # No race condition as with the deprecated tempfile.mktemp()
                # since tmp_dir is not world-writable.
                f = open(fName, "wb")
                f.write(text)
                f.close()

                # Ask for an empty title unless otherwise specified
                if not "title" in kwargs.keys():
                    kwargs["title"] = ""

                return self._perform(
                    *(["--textbox", fName, str(height), str(width)],),
                    **kwargs)[0]
            finally:
                if type(f) == types.FileType:
                    f.close()           # Safe, even several times
                    os.unlink(fName)
                os.rmdir(tmp_dir)
        except os.error, v:
            raise PythonDialogOSError(v.strerror)
        except IOError, v:
            raise PythonDialogIOError(v)

    def tailbox(self, filename, height=20, width=60, **kwargs):
        """Display the contents of a file in a dialog box, as in "tail -f".

        filename -- name of the file whose contents is to be
                    displayed in the box
        height   -- height of the box
        width    -- width of the box

        Display the contents of the specified file, updating the
        dialog box whenever the file grows, as with the "tail -f"
        command.

        Return the exit status (an integer) of the dialog-like
        program.

        Notable exceptions:

            any exception raised by self._perform()

	"""
	return self._perform(
            *(["--tailbox", filename, str(height), str(width)],),
            **kwargs)[0]
    # No tailboxbg widget, at least for now.

    def textbox(self, filename, height=20, width=60, **kwargs):
        """Display the contents of a file in a dialog box.

        filename -- name of the file whose contents is to be
                    displayed in the box
        height   -- height of the box
        width    -- width of the box

        A text box lets you display the contents of a text file in a
        dialog box. It is like a simple text file viewer. The user
        can move through the file by using the UP/DOWN, PGUP/PGDN
        and HOME/END keys available on most keyboards. If the lines
        are too long to be displayed in the box, the LEFT/RIGHT keys
        can be used to scroll the text region horizontally. For more
        convenience, forward and backward searching functions are
        also provided.

        Return the exit status (an integer) of the dialog-like
        program.

        Notable exceptions:

            any exception raised by self._perform()

	"""
        # This is for backward compatibility... not that it is
        # stupid, but I prefer explicit programming.
        if not "title" in kwargs.keys():
	    kwargs["title"] = filename
	return self._perform(
            *(["--textbox", filename, str(height), str(width)],),
            **kwargs)[0]

    def timebox(self, text, height=3, width=30, hour=-1, minute=-1,
                second=-1, **kwargs):
        """Display a time dialog box.

        text   -- text to display in the box
        height -- height of the box
        width  -- width of the box
        hour   -- inititial hour selected
        minute -- inititial minute selected
        second -- inititial second selected
        
        A dialog is displayed which allows you to select hour, minute
        and second. If the values for hour, minute or second are
        negative (or not explicitely provided, as they default to
        -1), the current time's corresponding values are used. You
        can increment or decrement any of those using the left-, up-,
        right- and down-arrows. Use tab or backtab to move between
        windows.

        Return a tuple of the form (code, time) where `code' is the
        exit status (an integer) of the dialog-like program and
        `time' is a list of the form [hour, minute, second] (where
        `hour', `minute' and `second' are integers corresponding to
        the time chosen by the user) if the box was closed with OK,
        or None if it was closed with the Cancel button.

        Notable exceptions:
            - any exception raised by self._perform()
            - PythonDialogReModuleError
            - UnexpectedDialogOutput

	"""
	(code, output) = self._perform(
            *(["--timebox", text, str(height), str(width),
               str(hour), str(minute), str(second)],),
            **kwargs)
        if code == self.DIALOG_OK:
            try:
                mo = _timebox_time_rec.match(output)
                if mo is None:
                    raise UnexpectedDialogOutput(
                        "the dialog-like program returned the following "
                        "unexpected time with the --timebox option: %s" % output)
                time = map(int, mo.group("hour", "minute", "second"))
            except re.error, v:
                raise PythonDialogReModuleError(v)
        else:
            time = None
        return (code, time)

    def yesno(self, text, height=10, width=30, **kwargs):
        """Display a yes/no dialog box.

        text   -- text to display in the box
        height -- height of the box
        width  -- width of the box

        A yes/no dialog box of size `height' rows by `width' columns
        will be displayed. The string specified by `text' is
        displayed inside the dialog box. If this string is too long
        to fit in one line, it will be automatically divided into
        multiple lines at appropriate places. The text string can
        also contain the sub-string "\\n" or newline characters to
        control line breaking explicitly. This dialog box is useful
        for asking questions that require the user to answer either
        yes or no. The dialog box has a Yes button and a No button,
        in which the user can switch between by pressing the TAB
        key.

        Return the exit status (an integer) of the dialog-like
        program.

        Notable exceptions:

            any exception raised by self._perform()

	"""
	return self._perform(
            *(["--yesno", text, str(height), str(width)],),
            **kwargs)[0]
