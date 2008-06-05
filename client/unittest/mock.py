__author__ = "raphtee@google.com (Travis Miller)"


import re, collections


class NoBackingFunctionError(Exception):
	pass


class argument_comparator(object):
	def is_satisfied_by(self, parameter):
		raise NotImplementedError


class equality_comparator(argument_comparator):
	def __init__(self, value):
		self.value = value


	def is_satisfied_by(self, parameter):
		return parameter == self.value


	def __str__(self):
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


class function_map(object):
	def __init__(self, symbol, return_val, *args, **dargs):
		self.return_val = return_val
		self.args = []
		self.symbol = symbol
		for arg in args:
			if isinstance(arg, argument_comparator):
				self.args.append(arg)
			else:
				self.args.append(equality_comparator(arg))

		self.dargs = dargs
		self.error = None


	def and_return(self, return_val):
		self.return_val = return_val


	def and_raises(self, error):
		self.error = error


	def match(self, *args, **dargs):
		if len(args) != len(self.args) or len(dargs) != len(self.dargs):
			return False

		for i, expected_arg in enumerate(self.args):
			if not expected_arg.is_satisfied_by(args[i]):
				return False

		if self.dargs != dargs:
			return False

		return True


	def __str__(self):
		return _dump_function_call(self.symbol, self.args, self.dargs)


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



	def __call__(self, *args, **dargs):
		self.num_calls += 1
		self.args.append(args)
		self.dargs.append(dargs)
		if self.playback:
			return self.playback(self.symbol, *args, **dargs)
		else:
			return self.default_return_val


	def expect_call(self, *args, **dargs):
		mapping = function_map(self.symbol, None, *args, **dargs)
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
		self.errors = []
		self.name = name
		self.record = record
		self.playback = playback

		for symbol in dir(cls):
			if symbol.startswith("_"):
				continue

			orig_symbol = getattr(cls, symbol)
			if callable(orig_symbol):
				f_name = "%s.%s" % (self.name, symbol)
				func = mock_function(f_name, default_ret_val,
					             self.record, self.playback)
				setattr(self, symbol, func)
			else:
				setattr(self, symbol, orig_symbol)



class mock_god:
	def __init__(self):
		self.recording = collections.deque()
		self.errors = []
		self._stubs = []


	def create_mock_class_obj(self, cls, name, default_ret_val=None):
		record = self.__record_call
		playback = self.__method_playback
		errors = self.errors

		class cls_sub(cls):
			cls_count = 0
			creations = collections.deque()

			# overwrite the initializer
			def __init__(self, *args, **dargs):
				pass


			@classmethod
			def expect_new(typ, *args, **dargs):
				obj = typ.make_new(*args, **dargs)
				typ.creations.append(obj)
				return obj


			def __new__(typ, *args, **dargs):
				if len(typ.creations) == 0:
					msg = ("not expecting call to %s "
					       "constructor" % (name))
					errors.append(msg)
					return None
				else:
					return typ.creations.popleft()


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
		assert hasattr(namespace, symbol)
		original_attribute = getattr(namespace, symbol)
		self._stubs.append((namespace, symbol, original_attribute))
		setattr(namespace, symbol, new_attribute)


	def stub_function(self, namespace, symbol):
		mock_attribute = self.create_mock_function(symbol)
		self.stub_with(namespace, symbol, mock_attribute)


	def unstub_all(self):
		self._stubs.reverse()
		for namespace, symbol, original_attribute in self._stubs:
			setattr(namespace, symbol, original_attribute)
		self._stubs = []


	def __method_playback(self, symbol, *args, **dargs):
		if len(self.recording) != 0:
			func_call = self.recording[0]
			if func_call.symbol != symbol:
				msg = ("Unexpected call: %s. Expected %s"
				    % (_dump_function_call(symbol, args, dargs),
				       func_call))
				self.errors.append(msg)
				return None

			if not func_call.match(*args, **dargs):
				msg = ("%s called. Expected %s"
				    % (_dump_function_call(symbol, args, dargs),
				      func_call))
				self.errors.append(msg)
				return None

			# this is the expected call so pop it and return
			self.recording.popleft()
			if func_call.error:
				raise func_call.error
			else:
				return func_call.return_val
		else:
			msg = ("unexpected call: %s"
			       % (_dump_function_call(symbol, args, dargs)))
			self.errors.append(msg)
			return None


	def __record_call(self, mapping):
		self.recording.append(mapping)


	def check_playback(self):
		"""
		Report any errors that were encounterd during calls
		to __method_playback().
		"""
		if len(self.errors) > 0:
			for error in self.errors:
				print error
			return False
		elif len(self.recording) != 0:
			for func_call in self.recording:
				print "%s not called" % (func_call)
			return False
		else:
			return True


def _dump_function_call(symbol, args, dargs):
	arg_vec = []
	for arg in args:
		arg_vec.append(str(arg))
	for key, val in dargs.iteritems():
		arg_vec.append("%s=%s" % (key,val))
	return "%s(%s)" % (symbol, ', '.join(arg_vec))
