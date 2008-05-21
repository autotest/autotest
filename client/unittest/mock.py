__author__ = "raphtee@google.com (Travis Miller)"


import collections


class argument_comparator(object):
	def is_satisfied_by(self, parameter):
		raise NotImplementedError


class equality_comparator(argument_comparator):
	def __init__(self, value):
		self.value = value


	def is_satisfied_by(self, parameter):
		return parameter == self.value


class is_string_comparator(argument_comparator):
	def is_satisfied_by(self, parameter):
		return isinstance(parameter, basestring)


class function_map(object):
	def __init__(self, return_val, *args, **dargs):
		self.return_val = return_val
		self.args = []
		for arg in args:
			if isinstance(arg, argument_comparator):
				self.args.append(arg)
			else:
				self.args.append(equality_comparator(arg))

		self.dargs = dargs


	def and_return(self, return_val):
		self.return_val = return_val	


	def match(self, *args, **dargs):
		if len(args) != len(self.args) or len(dargs) != len(self.dargs):
			return False

		for i, expected_arg in enumerate(self.args):
			return expected_arg.is_satisfied_by(args[i])

		if self.dargs != dargs:
			return False

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


	def __call__(self, *args, **dargs):
		self.num_calls += 1
		self.args.append(args)
		self.dargs.append(dargs)
		if self.playback:
			return self.playback(self.symbol, *args, **dargs)
		else:
			return self.default_return_val

	
	def expect_call(self, *args, **dargs):
		mapping = function_map(None, *args, **dargs)
		if self.record:
			self.record(self.symbol, mapping)
		else:
			self.default_return_val = mapping.return_val
		
		return mapping


class mock_class(object):
	def __init__(self, cls, name, default_ret_val=None, 
	             record=None, playback=None):
		self.errors = []
		self.name = name
		self.record = record
		self.playback = playback

		symbols = dir(cls)
		for symbol in symbols:
			if symbol.startswith("_"):
				continue
				
			if callable(getattr(cls, symbol)):
				f_name = "%s.%s" % (self.name, symbol)
				func = mock_function(f_name, default_ret_val,
					             self.record, self.playback)
				setattr(self, symbol, func)
			else:
				setattr(self, symbol, getattr(cls, symbol))


class mock_god:
	def __init__(self):
		self.recording = collections.deque()
		self.errors = []


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


	def __method_playback(self, symbol, *args, **dargs):
		if len(self.recording) != 0:
			func_call = self.recording[0]
			if func_call[0] != symbol:
				msg = ("unexpected call: %s args=%s dargs=%s\n"
				       "expected %s args=%s dargs=%s" 
				       % (symbol, args, dargs, func_call[0],
				         func_call[1].args, func_call[1].dargs))
				self.errors.append(msg)
				return None
			
			if not func_call[1].match(*args, **dargs):
				msg = ("%s called with args=%s dargs=%s\n" 
					"expected args=%s dargs=%s"
					% (symbol, args, dargs, 
					func_call[1].args, func_call[1].dargs))
				self.errors.append(msg)
				return None
				
			# this is the expected call so pop it and return
			self.recording.popleft()
			return func_call[1].return_val
		else:
			msg = ("unexpected call: %s args=%s dargs=%s\n"
			       % (symbol, args, dargs))
			self.errors.append(msg)
			return None


	def __record_call(self, symbol, mapping):
		self.recording.append((symbol, mapping))


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
				print "%s not called" % (func_call[0])
			return False
		else:
			return True
