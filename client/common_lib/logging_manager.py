import logging, os, signal, sys, warnings

# primary public APIs

def configure_logging(logging_config, **kwargs):
    """
    Configure the logging module using the specific configuration object, which
    should be an instance of logging_config.LoggingConfig (usually of a
    subclass).  Any keyword args will be passed to the object's
    configure_logging() method.

    Every entry point should call this method at application startup.
    """
    LoggingManager.logging_config_object = logging_config
    logging_config.configure_logging(**kwargs)


def get_logging_manager(manage_stdout_and_stderr=False, redirect_fds=False):
    """
    Create a LoggingManager that's managing sys.stdout and sys.stderr.

    Every entry point that wants to capture stdout/stderr and/or use
    LoggingManager to manage a stack of destinations should call this method
    at application startup.
    """
    if redirect_fds:
        manager = FdRedirectionLoggingManager()
    else:
        manager = LoggingManager()
    if manage_stdout_and_stderr:
        manager.manage_stdout()
        manager.manage_stderr()
    return manager


# implementation follows

logger = logging.getLogger()


def _current_handlers():
    return set(logger.handlers)


_caller_code_to_skip_in_logging_stack = set()


def do_not_report_as_logging_caller(func):
    """Decorator to annotate functions we will tell logging not to log."""
    # These are not the droids you are looking for.
    # You may go about your business.
    _caller_code_to_skip_in_logging_stack.add(func.func_code)
    return func


# Copied from Python 2.4 logging/__init__.py Logger.findCaller and enhanced.
# The logging code remains the same and compatible with this monkey patching
# through at least Python version 2.6.2.
def _logging_manager_aware_logger__find_caller(unused):
    """
    Find the stack frame of the caller so that we can note the source
    file name, line number and function name.
    """
    f = sys._getframe(2).f_back
    rv = "(unknown file)", 0, "(unknown function)"
    while hasattr(f, "f_code"):
        co = f.f_code
        filename = os.path.normcase(co.co_filename)
        if filename == logging._srcfile:
            f = f.f_back
            continue
        ### START additional code.
        if co in _caller_code_to_skip_in_logging_stack:
            f = f.f_back
            continue
        ### END additional code.
        rv = (filename, f.f_lineno, co.co_name)
        break
    return rv


if sys.version_info[:2] > (2, 6):
    warnings.warn('This module has not been reviewed for Python %s' %
                  sys.version)


# Monkey patch our way around logging's design...
_original_logger__find_caller = logging.Logger.findCaller
logging.Logger.findCaller = _logging_manager_aware_logger__find_caller


class LoggingFile(object):
    """
    File-like object that will receive messages pass them to the logging
    infrastructure in an appropriate way.
    """
    def __init__(self, prefix='', level=logging.DEBUG):
        """
        @param prefix - The prefix for each line logged by this object.
        """
        self._prefix = prefix
        self._level = level
        self._buffer = []


    @do_not_report_as_logging_caller
    def write(self, data):
        """"
        Writes data only if it constitutes a whole line. If it's not the case,
        store it in a buffer and wait until we have a complete line.
        @param data - Raw data (a string) that will be processed.
        """
        # splitlines() discards a trailing blank line, so use split() instead
        data_lines = data.split('\n')
        if len(data_lines) > 1:
            self._buffer.append(data_lines[0])
            self._flush_buffer()
        for line in data_lines[1:-1]:
            self._log_line(line)
        if data_lines[-1]:
            self._buffer.append(data_lines[-1])


    @do_not_report_as_logging_caller
    def _log_line(self, line):
        """
        Passes lines of output to the logging module.
        """
        logging.log(self._level, self._prefix + line)


    @do_not_report_as_logging_caller
    def _flush_buffer(self):
        if self._buffer:
            self._log_line(''.join(self._buffer))
            self._buffer = []


    @do_not_report_as_logging_caller
    def flush(self):
        self._flush_buffer()


class _StreamManager(object):
    """
    Redirects all output for some output stream (normally stdout or stderr) to
    the logging module by replacing the file objects with a new LoggingFile
    that calls logging.log().
    """
    def __init__(self, stream, level, stream_setter):
        """
        @param stream: stream object to manage
        @param level: level at which data written to the stream will be logged
        @param stream_setter: function accepting a stream object that will
                replace the given stream in its original location.
        """
        self._stream = stream
        self._level = level
        self._stream_setter = stream_setter
        self._logging_stream = None


    def _replace_with_logger(self):
        self._logging_stream = LoggingFile(level=self._level)
        self._stream_setter(self._logging_stream)


    def _restore_stream(self):
        self._stream_setter(self._stream)


    def flush(self):
        self._logging_stream.flush()


    def start_logging(self):
        """Start directing the stream to the logging module."""
        self._replace_with_logger()


    def stop_logging(self):
        """Restore the stream to its original settings."""
        self._restore_stream()


    def on_push_context(self, context):
        """
        Called when the logging manager is about to push a new context onto the
        stack and has changed logging settings.  The StreamHandler can modify
        the context to be saved before returning.
        """
        pass


    def on_restore_context(self, context):
        """
        Called when the logging manager is restoring a previous context.
        """
        pass



class LoggingManager(object):
    """
    Manages a stack of logging configurations, allowing clients to conveniently
    add and remove logging destinations.  Also keeps a list of StreamManagers
    to easily direct streams into the logging module.
    """

    STREAM_MANAGER_CLASS = _StreamManager

    logging_config_object = None

    def __init__(self):
        """
        This class should not ordinarily be constructed directly (other than in
        tests).  Use the module-global factory method get_logging_manager()
        instead.
        """
        if self.logging_config_object is None:
            raise RuntimeError('You must call configure_logging() before this')

        # _context_stack holds a stack of context dicts.  Each context dict
        # contains:
        # * old_handlers: list of registered logging Handlers
        # contexts may also be extended by _StreamHandlers
        self._context_stack = []
        self._streams = []
        self._started = False


    def manage_stream(self, stream, level, stream_setter):
        """
        Tells this manager to manage the given stream.  All data written to the
        stream will be directed to the logging module instead.  Must be called
        before start_logging().

        @param stream: stream to manage
        @param level: level to log data written to this stream
        @param stream_setter: function to set the stream to a new object
        """
        if self._started:
            raise RuntimeError('You must call this before start_logging()')
        self._streams.append(self.STREAM_MANAGER_CLASS(stream, level,
                                                       stream_setter))


    def _sys_stream_setter(self, stream_name):
        assert stream_name in ('stdout', 'stderr'), stream_name
        def set_stream(file_object):
            setattr(sys, stream_name, file_object)
        return set_stream


    def manage_stdout(self):
        self.manage_stream(sys.stdout, logging.INFO,
                           self._sys_stream_setter('stdout'))


    def manage_stderr(self):
        self.manage_stream(sys.stderr, self.logging_config_object.stderr_level,
                           self._sys_stream_setter('stderr'))


    def start_logging(self):
        """
        Begin capturing output to the logging module.
        """
        for stream_manager in self._streams:
            stream_manager.start_logging()
        self._started = True


    def stop_logging(self):
        """
        Restore output to its original state.
        """
        while self._context_stack:
            self._pop_context()

        for stream_manager in self._streams:
            stream_manager.stop_logging()

        self._started = False


    def _clear_all_handlers(self):
        for handler in _current_handlers():
            logger.removeHandler(handler)


    def _get_context(self):
        return {'old_handlers': _current_handlers()}


    def _push_context(self, context):
        for stream_manager in self._streams:
            stream_manager.on_push_context(context)
        self._context_stack.append(context)


    def _flush_all_streams(self):
        for stream_manager in self._streams:
            stream_manager.flush()


    def _add_log_handlers(self, add_handlers_fn):
        """
        Modify the logging module's registered handlers and push a new context
        onto the stack.
        @param add_handlers_fn: function to modify the registered logging
        handlers. Accepts a context dictionary which may be modified.
        """
        self._flush_all_streams()
        context = self._get_context()

        add_handlers_fn(context)

        self._push_context(context)


    class _TaggingFormatter(logging.Formatter):
        """
        Delegates to a given formatter, but prefixes each line of output with a
        tag.
        """
        def __init__(self, base_formatter, tag):
            self.base_formatter = base_formatter
            prefix = tag + ' : '
            self._fmt = base_formatter._fmt.replace('%(message)s',
                                                    prefix + '%(message)s')
            self.datefmt = base_formatter.datefmt


    def _add_tagging_formatter(self, tag):
        for handler in _current_handlers():
            tagging_formatter = self._TaggingFormatter(handler.formatter, tag)
            handler.setFormatter(tagging_formatter)


    def _do_redirect(self, stream=None, filename=None, level=None,
                     clear_other_handlers=False):
        """
        @param clear_other_handlers - if true, clear out all other logging
        handlers.
        """
        assert bool(stream) != bool(filename) # xor
        if not self._started:
            raise RuntimeError('You must call start_logging() before this')

        def add_handler(context):
            if clear_other_handlers:
                self._clear_all_handlers()

            if stream:
                handler = self.logging_config_object.add_stream_handler(stream)
            else:
                handler = self.logging_config_object.add_file_handler(filename)

            if level:
                handler.setLevel(level)

        self._add_log_handlers(add_handler)


    def redirect(self, filename):
        """Redirect output to the specified file"""
        self._do_redirect(filename=filename, clear_other_handlers=True)


    def redirect_to_stream(self, stream):
        """Redirect output to the given stream"""
        self._do_redirect(stream=stream, clear_other_handlers=True)


    def tee_redirect(self, filename, level=None):
        """Tee output to the specified file"""
        self._do_redirect(filename=filename, level=level)


    def tee_redirect_to_stream(self, stream):
        """Tee output to the given stream"""
        self._do_redirect(stream=stream)


    def tee_redirect_debug_dir(self, debug_dir, log_name=None, tag=None):
        """
        Tee output to a full new set of debug logs in the given directory.
        """
        def add_handlers(context):
            if tag:
                self._add_tagging_formatter(tag)
                context['tag_added'] = True
            self.logging_config_object.add_debug_file_handlers(
                    debug_dir, log_name=log_name)
        self._add_log_handlers(add_handlers)


    def _restore_context(self, context):
        for stream_handler in self._streams:
            stream_handler.on_restore_context(context)

        # restore logging handlers
        old_handlers = context['old_handlers']
        for handler in _current_handlers() - old_handlers:
            handler.close()
        self._clear_all_handlers()
        for handler in old_handlers:
            logger.addHandler(handler)

        if 'tag_added' in context:
            for handler in _current_handlers():
                tagging_formatter = handler.formatter
                handler.setFormatter(tagging_formatter.base_formatter)


    def _pop_context(self):
        self._flush_all_streams()
        context = self._context_stack.pop()
        self._restore_context(context)


    def undo_redirect(self):
        """
        Undo the last redirection (that hasn't yet been undone).

        If any subprocesses have been launched since the redirection was
        performed, they must have ended by the time this is called.  Otherwise,
        this will hang waiting for the logging subprocess to end.
        """
        if not self._context_stack:
            raise RuntimeError('No redirects to undo')
        self._pop_context()


    def restore(self):
        """
        Same as undo_redirect().  For backwards compatibility with
        fd_stack.
        """
        self.undo_redirect()


class _FdRedirectionStreamManager(_StreamManager):
    """
    Like StreamManager, but also captures output from subprocesses by modifying
    the underlying file descriptors.

    For the underlying file descriptors, we spawn a subprocess that writes all
    input to the logging module, and we point the FD to that subprocess.  As a
    result, every time we redirect output we need to spawn a new subprocess to
    pick up the new logging settings (without disturbing any existing processes
    using the old logging subprocess).

    If, one day, we could get all code using utils.run() and friends to launch
    subprocesses, we'd no longer need to handle raw FD output, and we could
    get rid of all this business with subprocesses.  Another option would be
    to capture all stray output to a single, separate destination.
    """
    def __init__(self, stream, level, stream_setter):
        if not hasattr(stream, 'fileno'):
            # with fake, in-process file objects, subprocess output won't be
            # captured. this should never happen in normal use, since the
            # factory methods will only pass sys.stdout and sys.stderr.
            raise ValueError("FdRedirectionLoggingManager won't work with "
                             "streams that aren't backed by file "
                             "descriptors")

        super(_FdRedirectionStreamManager, self).__init__(stream, level,
                                                          stream_setter)
        self._fd = stream.fileno()
        self._fd_copy_stream = None


    def _point_stream_handlers_to_copy(self):
        """
        point logging StreamHandlers that point to this stream to a safe
        copy of the underlying FD. otherwise, StreamHandler output will go
        to the logging subprocess, effectively getting doubly logged.
        """
        fd_copy = os.dup(self._fd)
        self._fd_copy_stream = os.fdopen(fd_copy, 'w')
        self._redirect_logging_stream_handlers(self._stream,
                                               self._fd_copy_stream)


    def _restore_stream_handlers(self):
        """ point logging StreamHandlers back to the original FD """
        self._redirect_logging_stream_handlers(self._fd_copy_stream,
                                               self._stream)
        self._fd_copy_stream.close()


    def _redirect_logging_stream_handlers(self, old_stream, new_stream):
        """
        Redirect all configured logging StreamHandlers pointing to
        old_stream to point to new_stream instead.
        """
        for handler in _current_handlers():
            points_to_stream = (isinstance(handler, logging.StreamHandler) and
                                hasattr(handler.stream, 'fileno') and
                                handler.stream.fileno() == old_stream.fileno())
            if points_to_stream:
                logger.removeHandler(handler)
                handler.close() # doesn't close the stream, just the handler

                new_handler = logging.StreamHandler(new_stream)
                new_handler.setLevel(handler.level)
                new_handler.setFormatter(handler.formatter)
                for log_filter in handler.filters:
                    new_handler.addFilter(log_filter)
                logger.addHandler(new_handler)


    def start_logging(self):
        super(_FdRedirectionStreamManager, self).start_logging()
        self._point_stream_handlers_to_copy()


    def stop_logging(self):
        super(_FdRedirectionStreamManager, self).stop_logging()
        self._restore_stream_handlers()


    def _spawn_logging_subprocess(self):
        """
        Spawn a subprocess to log all input to the logging module with the
        current settings, and direct output to it.
        """
        read_end, write_end = os.pipe()
        pid = os.fork()
        if pid: # parent
            os.close(read_end)
            os.dup2(write_end, self._fd) # point FD to the subprocess
            os.close(write_end)
            return pid
        else: # child
            try:
                os.close(write_end)
                # ensure this subprocess doesn't hold any pipes to others
                os.close(1)
                os.close(2)
                self._run_logging_subprocess(read_end) # never returns
            except:
                # don't let exceptions in the child escape
                try:
                    logging.exception('Logging subprocess died:')
                finally:
                    os._exit(1)


    def _run_logging_subprocess(self, read_fd):
        """
        Always run from a subprocess.  Read from read_fd and write to the
        logging module until EOF.
        """
        signal.signal(signal.SIGTERM, signal.SIG_DFL) # clear handler
        input_file = os.fdopen(read_fd, 'r')
        for line in iter(input_file.readline, ''):
            logging.log(self._level, line.rstrip('\n'))
        logging.debug('Logging subprocess finished')
        os._exit(0)


    def _context_id(self):
        return '%s_context' % id(self)


    def on_push_context(self, context):
        # adds a context dict for this stream, $id_context, with the following:
        # * old_fd: FD holding a copy of the managed FD before launching a new
        #   subprocess.
        # * child_pid: PID of the logging subprocess launched
        fd_copy = os.dup(self._fd)
        child_pid = self._spawn_logging_subprocess()
        my_context = {'old_fd': fd_copy, 'child_pid': child_pid}
        context[self._context_id()] = my_context


    def on_restore_context(self, context):
        my_context = context[self._context_id()]

        # shut down subprocess
        child_pid = my_context['child_pid']
        try:
            os.close(self._fd)
            os.waitpid(child_pid, 0)
        except OSError:
            logging.exception('Failed to cleanly shutdown logging subprocess:')

        # restore previous FD
        old_fd = my_context['old_fd']
        os.dup2(old_fd, self._fd)
        os.close(old_fd)


class FdRedirectionLoggingManager(LoggingManager):
    """
    A simple extension of LoggingManager to use FdRedirectionStreamManagers,
    so that managed streams have their underlying FDs redirected.
    """

    STREAM_MANAGER_CLASS = _FdRedirectionStreamManager

    def start_logging(self):
        super(FdRedirectionLoggingManager, self).start_logging()
        # spawn the initial logging subprocess
        self._push_context(self._get_context())


    def undo_redirect(self):
        # len == 1 would mean only start_logging() had been called (but no
        # redirects had occurred)
        if len(self._context_stack) < 2:
            raise RuntimeError('No redirects to undo')
        super(FdRedirectionLoggingManager, self).undo_redirect()
