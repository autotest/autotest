"""\
Utility functions for rpc_interface.py.  We keep them in a separate file so that
only RPC interface functions go into that file.
"""

__author__ = 'showard@google.com (Steve Howard)'

import datetime, xmlrpclib, threading
from frontend.afe import models

def prepare_for_serialization(objects):
	"""\
	Do necessary type conversions to values in data to allow for RPC
	serialization.
	-convert datetimes to strings
	"""
	objects = gather_unique_dicts(objects)
	new_objects = []
	for data in objects:
		new_data = {}
		for key, value in data.iteritems():
			if isinstance(value, datetime.datetime):
				new_data[key] = str(value)
			else:
				new_data[key] = value
		new_objects.append(new_data)
	return new_objects


def extra_job_filters(not_yet_run=False, running=False, finished=False):
	"""\
	Generate a SQL WHERE clause for job status filtering, and return it in
	a dict of keyword args to pass to query.extra().  No more than one of
	the parameters should be passed as True.
	"""
	assert not ((not_yet_run and running) or
		    (not_yet_run and finished) or
		    (running and finished)), ('Cannot specify more than one '
					      'filter to this function')
	if not_yet_run:
		where = ['id NOT IN (SELECT job_id FROM host_queue_entries '
			 'WHERE active OR complete)']
	elif running:
		where = ['(id IN (SELECT job_id FROM host_queue_entries '
			  'WHERE active OR complete)) AND '
			 '(id IN (SELECT job_id FROM host_queue_entries '
			  'WHERE not complete OR active))']
	elif finished:
		where = ['id NOT IN (SELECT job_id FROM host_queue_entries '
			 'WHERE not complete OR active)']
	else:
		return None
	return {'where': where}


local_vars = threading.local()

def set_user(user):
	"""\
	Sets the current request's logged-in user.  user should be a
	afe.models.User object.
	"""
        local_vars.user = user


def get_user():
	'Get the currently logged-in user as a afe.models.User object.'
        return local_vars.user


class InconsistencyException(Exception):
	'Raised when a list of objects does not have a consistent value'


def get_consistent_value(objects, field):
	value = getattr(objects[0], field)
	for obj in objects:
		this_value = getattr(obj, field)
		if this_value != value:
			raise InconsistencyException(objects[0], obj)
	return value


def prepare_generate_control_file(tests, kernel, label):
	test_objects = [models.Test.smart_get(test) for test in tests]
	# ensure tests are all the same type
	try:
		test_type = get_consistent_value(test_objects, 'test_type')
	except InconsistencyException, exc:
		test1, test2 = exc.args
		raise models.ValidationError(
		    {'tests' : 'You cannot run both server- and client-side '
		     'tests together (tests %s and %s differ' % (
		    test1.name, test2.name)})

	try:
		synch_type = get_consistent_value(test_objects, 'synch_type')
	except InconsistencyException, exc:
		test1, test2 = exc.args
		raise models.ValidationError(
		    {'tests' : 'You cannot run both synchronous and '
		     'asynchronous tests together (tests %s and %s differ)' % (
		    test1.name, test2.name)})

	is_server = (test_type == models.Test.Types.SERVER)
	is_synchronous = (synch_type == models.Test.SynchType.SYNCHRONOUS)
	if label:
		label = models.Label.smart_get(label)

	return is_server, is_synchronous, test_objects, label


def gather_unique_dicts(dict_iterable):
	"""\
	Pick out unique objects (by ID) from an iterable of object dicts.
	"""
	id_set = set()
	result = []
	for obj in dict_iterable:
		if obj['id'] not in id_set:
			id_set.add(obj['id'])
			result.append(obj)
	return result
