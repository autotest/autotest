"""\
Functions to expose over the RPC interface.

For all modify* and delete* functions that ask for an 'id' parameter to
identify the object to operate on, the id may be either
 * the database row ID
 * the name of the object (label name, hostname, user login, etc.)
 * a dictionary containing uniquely identifying field (this option should seldom
   be used)

When specifying foreign key fields (i.e. adding hosts to a label, or adding
users to an ACL group), the given value may be either the database row ID or the
name of the object.

All get* functions return lists of dictionaries.  Each dictionary represents one
object and maps field names to values.

Some examples:
modify_host(2, hostname='myhost') # modify hostname of host with database ID 2
modify_host('ipaj2', hostname='myhost') # modify hostname of host 'ipaj2'
modify_test('sleeptest', test_type='Client', params=', seconds=60')
delete_acl_group(1) # delete by ID
delete_acl_group('Everyone') # delete by name
acl_group_add_users('Everyone', ['mbligh', 'showard'])
get_jobs(owner='showard', status='Queued')

See doctests/rpc_test.txt for (lots) more examples.
"""

__author__ = 'showard@google.com (Steve Howard)'

import models, control_file, rpc_utils

# labels

def add_label(name, kernel_config=None, platform=None):
	return models.Label.add_object(name=name, kernel_config=kernel_config,
				       platform=platform).id


def modify_label(id, **data):
	models.Label.smart_get(id).update_object(data)


def delete_label(id):
	models.Label.smart_get(id).delete()


def get_labels(**filter_data):
	return rpc_utils.prepare_for_serialization(
	    models.Label.list_objects(filter_data))


# hosts

def add_host(hostname, status=None, locked=None):
	return models.Host.add_object(hostname=hostname, status=status,
				      locked=locked).id


def modify_host(id, **data):
	models.Host.smart_get(id).update_object(data)


def host_add_labels(id, labels):
	labels = [models.Label.smart_get(label) for label in labels]
	models.Host.smart_get(id).labels.add(*labels)


def host_remove_labels(id, labels):
	labels = [models.Label.smart_get(label) for label in labels]
	models.Host.smart_get(id).labels.remove(*labels)


def delete_host(id):
	models.Host.smart_get(id).delete()


def get_hosts(**filter_data):
	hosts = models.Host.list_objects(filter_data)
	for host in hosts:
		host_obj = models.Host.objects.get(id=host['id'])
		host['labels'] = [label.name
				  for label in host_obj.labels.all()]
                platform = host_obj.platform()
		host['platform'] = platform and platform.name or None
	return rpc_utils.prepare_for_serialization(hosts)


def get_num_hosts(**filter_data):
	return models.Host.query_count(filter_data)


# tests

def add_test(name, test_type, path, test_class=None, description=None):
	return models.Test.add_object(name=name, test_type=test_type, path=path,
				      test_class=test_class,
				      description=description).id


def modify_test(id, **data):
	models.Test.smart_get(id).update_object(data)


def delete_test(id):
	models.Test.smart_get(id).delete()


def get_tests(**filter_data):
	return rpc_utils.prepare_for_serialization(
	    models.Test.list_objects(filter_data))


# users

def add_user(login, access_level=None):
	return models.User.add_object(login=login, access_level=access_level).id


def modify_user(id, **data):
	models.User.smart_get(id).update_object(data)


def delete_user(id):
	models.User.smart_get(id).delete()


def get_users(**filter_data):
	return rpc_utils.prepare_for_serialization(
	    models.User.list_objects(filter_data))


# acl groups

def add_acl_group(name, description=None):
	return models.AclGroup.add_object(name=name, description=description).id


def modify_acl_group(id, **data):
	models.AclGroup.smart_get(id).update_object(data)


def acl_group_add_users(id, users):
	users = [models.User.smart_get(user) for user in users]
	models.AclGroup.smart_get(id).users.add(*users)


def acl_group_remove_users(id, users):
	users = [models.User.smart_get(user) for user in users]
	models.AclGroup.smart_get(id).users.remove(*users)


def acl_group_add_hosts(id, hosts):
	hosts = [models.Host.smart_get(host) for host in hosts]
	models.AclGroup.smart_get(id).hosts.add(*hosts)


def acl_group_remove_hosts(id, hosts):
	hosts = [models.Host.smart_get(host) for host in hosts]
	models.AclGroup.smart_get(id).hosts.remove(*hosts)


def delete_acl_group(id):
	models.AclGroup.smart_get(id).delete()


def get_acl_groups(**filter_data):
	acl_groups = models.AclGroup.list_objects(filter_data)
	for acl_group in acl_groups:
		acl_group_obj = models.AclGroup.objects.get(id=acl_group['id'])
		acl_group['users'] = [user.login
				      for user in acl_group_obj.users.all()]
		acl_group['hosts'] = [host.hostname
				      for host in acl_group_obj.hosts.all()]
	return rpc_utils.prepare_for_serialization(acl_groups)


# jobs

def generate_control_file(tests, kernel=None, label=None):
	"""\
	Generates a client-side control file to load a kernel and run a set of
	tests.  Returns a tuple (control_file, is_server, is_synchronous):
	control_file - the control file text
	is_server - is the control file a server-side control file?
	is_synchronous - should the control file be run synchronously?

	tests: list of tests to run
	kernel: kernel to install in generated control file
	label: name of label to grab kernel config from
	"""
	if not tests:
		return '', False, False

	is_server, is_synchronous, test_objects, label = (
	    rpc_utils.prepare_generate_control_file(tests, kernel, label))
	cf_text = control_file.generate_control(test_objects, kernel, label,
                                                is_server)
	return cf_text, is_server, is_synchronous


def create_job(name, priority, control_file, control_type, is_synchronous=None,
	       hosts=None, meta_hosts=None):
	"""\
	Create and enqueue a job.

	priority: Low, Medium, High, Urgent
	control_file: contents of control file
	control_type: type of control file, Client or Server
	is_synchronous: boolean indicating if a job is synchronous
	hosts: list of hosts to run job on
	meta_hosts: list where each entry is a label name, and for each entry
	            one host will be chosen from that label to run the job
		    on.
	"""
        owner = rpc_utils.get_user().login
	# input validation
	if not hosts and not meta_hosts:
		raise models.ValidationError({
		    'arguments' : "You must pass at least one of 'hosts' or "
		                  "'meta_hosts'"
		    })

	# convert hostnames & meta hosts to host/label objects
	host_objects = []
	for host in hosts or []:
		this_host = models.Host.smart_get(host)
		host_objects.append(this_host)
	for label in meta_hosts or []:
		this_label = models.Label.smart_get(label)
		host_objects.append(this_label)

	# default is_synchronous to some appropriate value
	ControlType = models.Job.ControlType
	control_type = ControlType.get_value(control_type)
	if is_synchronous is None:
		is_synchronous = (control_type == ControlType.SERVER)
	# convert the synch flag to an actual type
	if is_synchronous:
		synch_type = models.Test.SynchType.SYNCHRONOUS
	else:
		synch_type = models.Test.SynchType.ASYNCHRONOUS

	job = models.Job.create(owner=owner, name=name, priority=priority,
				control_file=control_file,
				control_type=control_type,
				synch_type=synch_type,
				hosts=host_objects)
	job.queue(host_objects)
	return job.id


def requeue_job(id):
	"""\
	Create and enqueue a copy of the given job.
	"""
	job = models.Job.objects.get(id=id)
	new_job = job.requeue(rpc_utils.get_user().login)
	return new_job.id


def abort_job(id):
	"""\
	Abort the job with the given id number.
	"""
	job = models.Job.objects.get(id=id)
	job.abort()


def get_jobs(not_yet_run=False, running=False, finished=False, **filter_data):
	"""\
	Extra filter args for get_jobs:
        -not_yet_run: Include only jobs that have not yet started running.
        -running: Include only jobs that have start running but for which not
        all hosts have completed.
        -finished: Include only jobs for which all hosts have completed (or
        aborted).
        At most one of these fields should be specified.
	"""
	filter_data['extra_args'] = rpc_utils.extra_job_filters(not_yet_run,
								running,
								finished)
	return rpc_utils.prepare_for_serialization(
	    models.Job.list_objects(filter_data))


def get_num_jobs(not_yet_run=False, running=False, finished=False,
		 **filter_data):
	"""\
        See get_jobs() for documentation of extra filter parameters.
        """
	return models.Job.query_count(filter_data)


def job_status(job_id, **filter_data):
	"""\
	Get status of job with the given id number.  Returns a dictionary
	mapping hostnames to dictionaries with two keys each:
	 * 'status' : the job status for that host
	 * 'meta_count' : For meta host entires, gives a count of how many
	                  entries there are for this label (the hostname is
			  then a label name).  For real host entries,
			  meta_count is None.
	"""
	filter_data['job'] = job_id
	job_entries = models.HostQueueEntry.query_objects(filter_data)
	hosts_status = {}
	for queue_entry in job_entries:
		is_meta = queue_entry.is_meta_host_entry()
		if is_meta:
			name = queue_entry.meta_host.name
			hosts_status.setdefault(name, {'meta_count': 0})
			hosts_status[name]['meta_count'] += 1
		else:
			name = queue_entry.host.hostname
			hosts_status[name] = {'meta_count': None}
		hosts_status[name]['status'] = queue_entry.status
	return hosts_status


def job_num_entries(job_id, **filter_data):
	"""\
	Get the number of host queue entries associated with this job.
	"""
	filter_data['job'] = job_id
	return models.HostQueueEntry.query_count(filter_data)


def get_jobs_summary(**filter_data):
	"""\
	Like get_jobs(), but adds a 'stauts_counts' field, which is a dictionary
	mapping status strings to the number of hosts currently with that
	status, i.e. {'Queued' : 4, 'Running' : 2}.
	"""
	jobs = get_jobs(**filter_data)
	ids = [job['id'] for job in jobs]
	all_status_counts = models.Job.objects.get_status_counts(ids)
	for job in jobs:
		job['status_counts'] = all_status_counts[job['id']]
	return rpc_utils.prepare_for_serialization(jobs)


# other

def get_static_data():
	"""\
	Returns a dictionary containing a bunch of data that shouldn't change
	often.  This includes:
	priorities: list of job priority choices
	default_priority: default priority value for new jobs
	users: sorted list of all usernames
	labels: sorted list of all label names
	tests: sorted list of all test names
	user_login: logged-in username
	"""
	result = {}
	result['priorities'] = models.Job.Priority.choices()
	default_priority = models.Job.get_field_dict()['priority'].default
	default_string = models.Job.Priority.get_string(default_priority)
	result['default_priority'] = default_string
	result['users'] = [user.login for user in
			   models.User.objects.all().order_by('login')]
	result['labels'] = [label.name for label in
			    models.Label.objects.all().order_by('name')]
	result['tests'] = get_tests(sort_by='name')
	result['user_login'] = rpc_utils.get_user().login
	result['host_statuses'] = models.Host.Status.names
	result['job_statuses'] = models.Job.Status.names
	return result
