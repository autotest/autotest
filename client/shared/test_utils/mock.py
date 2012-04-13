__author__ = "raphtee@google.com (Travis Miller)"


import re, collections, StringIO, sys, unittest


class StubNotFoundError(Exception):
    'Raised when god is asked to unstub an attribute that was not stubbed'
    pass


class CheckPlaybackError(Exception):
    'Raised when mock playback does not match recorded calls.'
    pass


class SaveDataAfterCloseStringIO(StringIO.StringIO):
    """Saves the contents in a final_data property when close() is called.

    Useful as a mock output file object to test both that the file was
    closed and what was written.

    Properties:
      final_data: Set to the StringIO's getvalue() data when close() is
          called.  None if close() has not been called.
    """
    final_data = None

    def close(self):
        self.final_data = self.getvalue()
        StringIO.StringIO.close(self)



class argument_comparator(object):
    def is_satisfied_by(self, parameter):
        raise NotImplementedError


class equality_comparator(argument_comparator):
    def __init__(self, value):
        self.value = value


    @staticmethod
    def _types_match(arg1, arg2):
        if isinstance(arg1, basestring) and isinstance(arg2, basestring):
            return True
        return type(arg1) == type(arg2)


    @classmethod
    def _compare(cls, actual_arg, expected_arg):
        if isinstance(expected_arg, argument_comparator):
            return expected_arg.is_satisfied_by(actual_arg)
        if not cls._types_match(expected_arg, actual_arg):
            return False

        if isinstance(expected_arg, list) or isinstance(expected_arg, tuple):
            # recurse on lists/tuples
            if len(actual_arg) != len(expected_arg):
                return False
            for actual_item, expected_item in zip(actual_arg, expected_arg):
                if not cls._compare(actual_item, expected_item):
                    return False
        elif isinstance(expected_arg, dict):
            # recurse on dicts
            if not cls._compare(sorted(actual_arg.keys()),
                                sorted(expected_arg.keys())):
                return False
            for key, value in actual_arg.iteritems():
                if not cls._compare(value, expected_arg[key]):
                    return False
        elif actual_arg != expected_arg:
            return False

        return True


    def is_satisfied_by(self, parameter):
        return self._compare(parameter, self.value)


    def __str__(self):
        if isinstance(self.value, argument_comparator):
            return str(self.value)
        return repr(self.value)


class regex_comparator(argument_comparator):
    def __init__(self, pattern, flags=0):
        self.regex = re.compile(pattern, flags)


    def is_satisfied_by(self, parameter):
        return self.regex.search(parameter) is not None


    def __str__(self):
        return self.regex.pattern


class is_string_comparator(argument_comparator):
    def is_satisfied_by(self, parameter):
        return isinstance(parameter, basestring)


    def __str__(self):
        return "a string"


class is_instance_comparator(argument_comparator):
    def __init__(self, cls):
        self.cls = cls


    def is_satisfied_by(self, parameter):
        return isinstance(parameter, self.cls)


    def __str__(self):
        return "is a %s" % self.cls


class anything_comparator(argument_comparator):
    def is_satisfied_by(self, parameter):
        return True


    def __str__(self):
        return 'anything'


class base_mapping(object):
    def __init__(self, symbol, return_obj, *args, **dargs):
        self.return_obj = return_obj
        self.symbol = symbol
        self.args = [equality_comparator(arg) for arg in args]
        self.dargs = dict((key, equality_comparator(value))
                          for key, value in dargs.iteritems())
        self.error = None


    def match(self, *args, **dargs):
        if len(args) != len(self.args) or len(dargs) != len(self.dargs):
            return False

        for i, expected_arg in enumerate(self.args):
            if not expected_arg.is_satisfied_by(args[i]):
                return False

        # check for incorrect dargs
        for key, value in dargs.iteritems():
            if key not in self.dargs:
                return False
            if not self.dargs[key].is_satisfied_by(value):
                return False

        # check for missing dargs
        for key in self.dargs.iterkeys():
            if key not in dargs:
                return False

        return True


    def __str__(self):
        return _dump_function_call(self.symbol, self.args, self.dargs)


class function_mapping(base_mapping):
    def __init__(self, symbol, return_val, *args, **dargs):
        super(function_mapping, self).__init__(symbol, return_val, *args,
                                               **dargs)


    def and_return(self, return_obj):
        self.return_obj = return_obj


    def and_raises(self, error):
        self.error = error


class function_any_args_mapping(function_mapping):
    """A mock function mapping that doesn't verify its arguments."""
    def match(self, *args, **dargs):
        return True


class mock_function(object):
    def __init__(self, symbol, default_return_val=None,
                 record=None, playback=None):
        self.default_return_val = default_return_val
        self.num_calls = 0
        self.args = []
        self.dargs = []
        self.symbol = symbol
        self.record = record
        self.playback = playback
        self.__name__ = symbol


    def __call__(self, *args, **dargs):
        self.num_calls += 1
        self.args.append(args)
        self.dargs.append(dargs)
        if self.playback:
            return self.playback(self.symbol, *args, **dargs)
        else:
            return self.default_return_val


    def expect_call(self, *args, **dargs):
        mapping = function_mapping(self.symbol, None, *args, **dargs)
        if self.record:
            self.record(mapping)

        return mapping


    def expect_any_call(self):
        """Like expect_call but don't give a hoot what arguments are passed."""
        mapping = function_any_args_mapping(self.symbol, None)
        if self.record:
            self.record(mapping)

        return mapping


class mask_function(mock_function):
    def __init__(self, symbol, original_function, default_return_val=None,
                 record=None, playback=None):
        super(mask_function, self).__init__(symbol,
                                            default_return_val,
                                            record, playback)
        self.original_function = original_function


    def run_original_function(self, *args, **dargs):
        return self.original_function(*args, **dargs)


class mock_class(object):
    def __init__(self, cls, name, default_ret_val=None,
                 record=None, playback=None):
        self.__name = name
        self.__record = record
        self.__playback = playback

        for symbol in dir(cls):
            if symbol.startswith("_"):
                continue

            orig_symbol = getattr(cls, symbol)
            if callable(orig_symbol):
                f_name = "%s.%s" % (self.__name, symbol)
                func = mock_function(f_name, default_ret_val,
                                     self.__record, self.__playback)
                setattr(self, symbol, func)
            else:
                setattr(self, symbol, orig_symbol)


    def __repr__(self):
        return '<mock_class: %s>' % self.__name


class mock_god(object):
    NONEXISTENT_ATTRIBUTE = object()

    def __init__(self, debug=False, fail_fast=True, ut=None):
        """
        With debug=True, all recorded method calls will be printed as
        they happen.
        With fail_fast=True, unexpected calls will immediately cause an
        exception to be raised.  With False, they will be silently recorded and
        only reported when check_playback() is called.
        """
        self.recording = collections.deque()
        self.errors = []
        self._stubs = []
        self._debug = debug
        self._fail_fast = fail_fast
        self._ut = ut


    def set_fail_fast(self, fail_fast):
        self._fail_fast = fail_fast


    def create_mock_class_obj(self, cls, name, default_ret_val=None):
        record = self.__record_call
        playback = self.__method_playback
        errors = self.errors

        class cls_sub(cls):
            cls_count = 0

            # overwrite the initializer
            def __init__(self, *args, **dargs):
                pass


            @classmethod
            def expect_new(typ, *args, **dargs):
                obj = typ.make_new(*args, **dargs)
                mapping = base_mapping(name, obj, *args, **dargs)
                record(mapping)
                return obj


            def __new__(typ, *args, **dargs):
                return playback(name, *args, **dargs)


            @classmethod
            def make_new(typ, *args, **dargs):
                obj = super(cls_sub, typ).__new__(typ, *args,
                                                  **dargs)

                typ.cls_count += 1
                obj_name = "%s_%s" % (name, typ.cls_count)
                for symbol in dir(obj):
                    if (symbol.startswith("__") and
                        symbol.endswith("__")):
                        continue

                    if isinstance(getattr(typ, symbol, None), property):
                        continue

                    orig_symbol = getattr(obj, symbol)
                    if callable(orig_symbol):
                        f_name = ("%s.%s" %
                                  (obj_name, symbol))
                        func = mock_function(f_name,
                                        default_ret_val,
                                        record,
                                        playback)
                        setattr(obj, symbol, func)
                    else:
                        setattr(obj, symbol,
                                orig_symbol)

                return obj

        return cls_sub


    def create_mock_class(self, cls, name, default_ret_val=None):
        """
        Given something that defines a namespace cls (class, object,
        module), and a (hopefully unique) name, will create a
        mock_class object with that name and that possessess all
        the public attributes of cls.  default_ret_val sets the
        default_ret_val on all methods of the cls mock.
        """
        return mock_class(cls, name, default_ret_val,
                          self.__record_call, self.__method_playback)


    def create_mock_function(self, symbol, default_return_val=None):
        """
        create a mock_function with name symbol and default return
        value of default_ret_val.
        """
        return mock_function(symbol, default_return_val,
                             self.__record_call, self.__method_playback)


    def mock_up(self, obj, name, default_ret_val=None):
        """
        Given an object (class instance or module) and a registration
        name, then replace all its methods with mock function objects
        (passing the orignal functions to the mock functions).
        """
        for symbol in dir(obj):
            if symbol.startswith("__"):
                continue

            orig_symbol = getattr(obj, symbol)
            if callable(orig_symbol):
                f_name = "%s.%s" % (name, symbol)
                func = mask_function(f_name, orig_symbol,
                                     default_ret_val,
                                     self.__record_call,
                                     self.__method_playback)
                setattr(obj, symbol, func)


    def stub_with(self, namespace, symbol, new_attribute):
        original_attribute = getattr(namespace, symbol,
                                     self.NONEXISTENT_ATTRIBUTE)

        # You only want to save the original attribute in cases where it is
        # directly associated with the object in question. In cases where
        # the attribute is actually inherited via some sort of hierarchy
        # you want to delete the stub (restoring the original structure)
        attribute_is_inherited = (hasattr(namespace, '__dict__') and
                                  symbol not in namespace.__dict__)
        if attribute_is_inherited:
            original_attribute = self.NONEXISTENT_ATTRIBUTE

        newstub = (namespace, symbol, original_attribute, new_attribute)
        self._stubs.append(newstub)
        setattr(namespace, symbol, new_attribute)


    def stub_function(self, namespace, symbol):
        mock_attribute = self.create_mock_function(symbol)
        self.stub_with(namespace, symbol, mock_attribute)


    def stub_class_method(self, cls, symbol):
        mock_attribute = self.create_mock_function(symbol)
        self.stub_with(cls, symbol, staticmethod(mock_attribute))


    def stub_class(self, namespace, symbol):
        attr = getattr(namespace, symbol)
        mock_class = self.create_mock_class_obj(attr, symbol)
        self.stub_with(namespace, symbol, mock_class)


    def stub_function_to_return(self, namespace, symbol, object_to_return):
        """Stub out a function with one that always returns a fixed value.

        @param namespace The namespace containing the function to stub out.
        @param symbol The attribute within the namespace to stub out.
        @param object_to_return The value that the stub should return whenever
            it is called.
        """
        self.stub_with(namespace, symbol,
                       lambda *args, **dargs: object_to_return)


    def _perform_unstub(self, stub):
        namespace, symbol, orig_attr, new_attr = stub
        if orig_attr == self.NONEXISTENT_ATTRIBUTE:
            delattr(namespace, symbol)
        else:
            setattr(namespace, symbol, orig_attr)


    def unstub(self, namespace, symbol):
        for stub in reversed(self._stubs):
            if (namespace, symbol) == (stub[0], stub[1]):
                self._perform_unstub(stub)
                self._stubs.remove(stub)
                return

        raise StubNotFoundError()


    def unstub_all(self):
        self._stubs.reverse()
        for stub in self._stubs:
            self._perform_unstub(stub)
        self._stubs = []


    def __method_playback(self, symbol, *args, **dargs):
        if self._debug:
            print >> sys.__stdout__, (' * Mock call: ' +
                                      _dump_function_call(symbol, args, dargs))

        if len(self.recording) != 0:
            func_call = self.recording[0]
            if func_call.symbol != symbol:
                msg = ("Unexpected call: %s\nExpected: %s"
                    % (_dump_function_call(symbol, args, dargs),
                       func_call))
                self._append_error(msg)
                return None

            if not func_call.match(*args, **dargs):
                msg = ("Incorrect call: %s\nExpected: %s"
                    % (_dump_function_call(symbol, args, dargs),
                      func_call))
                self._append_error(msg)
                return None

            # this is the expected call so pop it and return
            self.recording.popleft()
            if func_call.error:
                raise func_call.error
            else:
                return func_call.return_obj
        else:
            msg = ("unexpected call: %s"
                   % (_dump_function_call(symbol, args, dargs)))
            self._append_error(msg)
            return None


    def __record_call(self, mapping):
        self.recording.append(mapping)


    def _append_error(self, error):
        if self._debug:
            print >> sys.__stdout__, ' *** ' + error
        if self._fail_fast:
            raise CheckPlaybackError(error)
        self.errors.append(error)


    def check_playback(self):
        """
        Report any errors that were encounterd during calls
        to __method_playback().
        """
        if len(self.errors) > 0:
            if self._debug:
                print '\nPlayback errors:'
            for error in self.errors:
                print >> sys.__stdout__, error

            if self._ut:
                self._ut.fail('\n'.join(self.errors))

            raise CheckPlaybackError
        elif len(self.recording) != 0:
            errors = []
            for func_call in self.recording:
                error = "%s not called" % (func_call,)
                errors.append(error)
                print >> sys.__stdout__, error

            if self._ut:
                self._ut.fail('\n'.join(errors))

            raise CheckPlaybackError
        self.recording.clear()


    def mock_io(self):
        """Mocks and saves the stdout & stderr output"""
        self.orig_stdout = sys.stdout
        self.orig_stderr = sys.stderr

        self.mock_streams_stdout = StringIO.StringIO('')
        self.mock_streams_stderr = StringIO.StringIO('')

        sys.stdout = self.mock_streams_stdout
        sys.stderr = self.mock_streams_stderr


    def unmock_io(self):
        """Restores the stdout & stderr, and returns both
        output strings"""
        sys.stdout = self.orig_stdout
        sys.stderr = self.orig_stderr
        values = (self.mock_streams_stdout.getvalue(),
                  self.mock_streams_stderr.getvalue())

        self.mock_streams_stdout.close()
        self.mock_streams_stderr.close()
        return values


def _arg_to_str(arg):
    if isinstance(arg, argument_comparator):
        return str(arg)
    return repr(arg)


def _dump_function_call(symbol, args, dargs):
    arg_vec = []
    for arg in args:
        arg_vec.append(_arg_to_str(arg))
    for key, val in dargs.iteritems():
        arg_vec.append("%s=%s" % (key, _arg_to_str(val)))
    return "%s(%s)" % (symbol, ', '.join(arg_vec))
