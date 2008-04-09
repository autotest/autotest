import datetime
from django.db import models as dbmodels
from frontend.afe import enum
from frontend import settings


class ValidationError(Exception):
	"""\
	Data validation error in adding or updating an object.  The associated
	value is a dictionary mapping field names to error strings.
	"""


class AclAccessViolation(Exception):
	"""\
	Raised when an operation is attempted with proper permissions as
	dictated by ACLs.
	"""


class ModelExtensions(object):
	"""\
	Mixin with convenience functions for models, built on top of the
	default Django model functions.
	"""
	# TODO: at least some of these functions really belong in a custom
	# Manager class

	field_dict = None
	# subclasses should override if they want to support smart_get() by name
	name_field = None


	@classmethod
	def get_field_dict(cls):
		if cls.field_dict is None:
			cls.field_dict = {}
			for field in cls._meta.fields:
				cls.field_dict[field.name] = field
		return cls.field_dict


	@classmethod
	def clean_foreign_keys(cls, data):
		"""\
		Convert foreign key fields in data from <field>_id to just
		<field>
		"""
		for field in cls._meta.fields:
			if field.rel:
				data[field.name] = data[field.column]
				del data[field.column]


	# TODO(showard) - is there a way to not have to do this?
	@classmethod
	def provide_default_values(cls, data):
		"""\
		Provide default values for fields with default values which have
		nothing passed in.

		For CharField and TextField fields with "blank=True", if nothing
		is passed, we fill in an empty string value, even if there's no
		default set.
		"""
		new_data = dict(data)
		field_dict = cls.get_field_dict()
		for name, obj in field_dict.iteritems():
			if data.get(name) is not None:
				continue
			if obj.default is not dbmodels.fields.NOT_PROVIDED:
				new_data[name] = obj.default
			elif (isinstance(obj, dbmodels.CharField) or
			      isinstance(obj, dbmodels.TextField)):
				new_data[name] = ''
		return new_data


	@classmethod
	def convert_human_readable_values(cls, data, to_human_readable=False):
		"""\
		Performs conversions on user-supplied field data, to make it
		easier for users to pass human-readable data.

		For all fields that have choice sets, convert their values
		from human-readable strings to enum values, if necessary.  This
		allows users to pass strings instead of the corresponding
		integer values.

		For all foreign key fields, call smart_get with the supplied
		data.  This allows the user to pass either an ID value or
		the name of the object as a string.

		If to_human_readable=True, perform the inverse - i.e. convert
		numeric values to human readable values.
		"""
		new_data = dict(data)
		field_dict = cls.get_field_dict()
		for field_name in data:
			field_obj = field_dict[field_name]
			# convert enum values
			if field_obj.choices:
				for choice_data in field_obj.choices:
					# choice_data is (value, name)
					if to_human_readable:
						from_val, to_val = choice_data
					else:
						to_val, from_val = choice_data
					if from_val == data[field_name]:
						new_data[field_name] = to_val
						break
			# convert foreign key values
			elif field_obj.rel:
				dest_obj = field_obj.rel.to.smart_get(
				    data[field_name])
				if to_human_readable:
					new_data[field_name] = (
					    getattr(dest_obj,
						    dest_obj.name_field))
				else:
					new_data[field_name] = dest_obj.id
		return new_data


	@classmethod
	def validate_field_names(cls, data):
		'Checks for extraneous fields in data.'
		errors = {}
		field_dict = cls.get_field_dict()
		for field_name in data:
			if field_name not in field_dict:
				errors[field_name] = 'No field of this name'
		return errors


	@classmethod
	def prepare_data_args(cls, data, kwargs):
		'Common preparation for add_object and update_object'
		data = dict(data) # don't modify the default keyword arg
		data.update(kwargs)
		# must check for extraneous field names here, while we have the
		# data in a dict
		errors = cls.validate_field_names(data)
		if errors:
			raise ValidationError(errors)
		data = cls.convert_human_readable_values(data)
		return data


	def validate_unique(self):
		"""\
		Validate that unique fields are unique.  Django manipulators do
		this too, but they're a huge pain to use manually.  Trust me.
		"""
		errors = {}
		cls = type(self)
		field_dict = self.get_field_dict()
		for field_name, field_obj in field_dict.iteritems():
			if not field_obj.unique:
				continue

			value = getattr(self, field_name)
			existing_objs = cls.objects.filter(
			    **{field_name : value})
			num_existing = existing_objs.count()

			if num_existing == 0:
				continue
			if num_existing == 1 and existing_objs[0].id == self.id:
				continue
			errors[field_name] = (
			    'This value must be unique (%s)' % (value))
		return errors


	def do_validate(self):
		errors = self.validate()
		unique_errors = self.validate_unique()
		for field_name, error in unique_errors.iteritems():
			errors.setdefault(field_name, error)
		if errors:
			raise ValidationError(errors)


	# actually (externally) useful methods follow

	@classmethod
	def add_object(cls, data={}, **kwargs):
		"""\
		Returns a new object created with the given data (a dictionary
		mapping field names to values). Merges any extra keyword args
		into data.
		"""
		data = cls.prepare_data_args(data, kwargs)
		data = cls.provide_default_values(data)
		obj = cls(**data)
		obj.do_validate()
		obj.save()
		return obj


	def update_object(self, data={}, **kwargs):
		"""\
		Updates the object with the given data (a dictionary mapping
		field names to values).  Merges any extra keyword args into
		data.
		"""
		data = self.prepare_data_args(data, kwargs)
		for field_name, value in data.iteritems():
			if value is not None:
				setattr(self, field_name, value)
		self.do_validate()
		self.save()


	@classmethod
	def query_objects(cls, filter_data):
		"""\
		Returns a QuerySet object for querying the given model_class
		with the given filter_data.  Optional special arguments in
		filter_data include:
		-query_start: index of first return to return
		-query_limit: maximum number of results to return
		-sort_by: list of fields to sort on.  prefixing a '-' onto a
		 field name changes the sort to descending order.
		-extra_args: keyword args to pass to query.extra() (see Django
		 DB layer documentation)
		"""
		query_start = filter_data.pop('query_start', None)
		query_limit = filter_data.pop('query_limit', None)
		if query_start and not query_limit:
			raise ValueError('Cannot pass query_start without '
					 'query_limit')
		sort_by = filter_data.pop('sort_by', [])
		extra_args = filter_data.pop('extra_args', None)
		query_dict = {}
		for field, value in filter_data.iteritems():
			query_dict[field] = value
		query = cls.objects.filter(**query_dict)
		if extra_args:
			query = query.extra(**extra_args)
		assert isinstance(sort_by, list) or isinstance(sort_by, tuple)
		query = query.order_by(*sort_by)
		if query_start is not None and query_limit is not None:
			query_limit += query_start
		return query[query_start:query_limit]


	@classmethod
	def query_count(cls, filter_data):
		"""\
		Like query_objects, but retreive only the count of results.
		"""
		filter_data.pop('query_start', None)
		filter_data.pop('query_limit', None)
		return cls.query_objects(filter_data).count()


	@classmethod
	def clean_object_dicts(cls, field_dicts):
		"""\
		Take a list of dicts corresponding to object (as returned by
		query.values()) and clean the data to be more suitable for
		returning to the user.
		"""
		for i in range(len(field_dicts)):
			cls.clean_foreign_keys(field_dicts[i])
			field_dicts[i] = cls.convert_human_readable_values(
			    field_dicts[i], to_human_readable=True)


	@classmethod
	def list_objects(cls, filter_data):
		"""\
		Like query_objects, but return a list of dictionaries.
		"""
		query = cls.query_objects(filter_data)
		field_dicts = list(query.values())
		cls.clean_object_dicts(field_dicts)
		return field_dicts


	@classmethod
	def smart_get(cls, *args, **kwargs):
		"""\
		smart_get(integer) -> get object by ID
		smart_get(string) -> get object by name_field
		smart_get(keyword args) -> normal ModelClass.objects.get()
		"""
		assert bool(args) ^ bool(kwargs)
		if args:
			assert len(args) == 1
			arg = args[0]
			if isinstance(arg, int) or isinstance(arg, long):
				return cls.objects.get(id=arg)
			if isinstance(arg, str) or isinstance(arg, unicode):
				return cls.objects.get(
				    **{cls.name_field : arg})
			raise ValueError(
			    'Invalid positional argument: %s (%s)' % (
			    str(arg), type(arg)))
		return cls.objects.get(**kwargs)


	def get_object_dict(self):
		"""\
		Return a dictionary mapping fields to this object's values.
		"""
		return dict((field_name, getattr(self, field_name))
			    for field_name in self.get_field_dict().iterkeys())


class Label(dbmodels.Model, ModelExtensions):
	"""\
	Required:
	name: label name

	Optional:
	kernel_config: url/path to kernel config to use for jobs run on this
	               label
	platform: if True, this is a platform label (defaults to False)
	"""
	name = dbmodels.CharField(maxlength=255, unique=True)
	kernel_config = dbmodels.CharField(maxlength=255, blank=True)
	platform = dbmodels.BooleanField(default=False)

	name_field = 'name'


	def enqueue_job(self, job):
		'Enqueue a job on any host of this label.'
		queue_entry = HostQueueEntry(meta_host=self, job=job,
					     status=Job.Status.QUEUED,
					     priority=job.priority)
		queue_entry.save()


	def block_auto_assign(self, job):
		"""\
		Placeholder to allow labels to be used in place of hosts
		(as meta-hosts).
		"""
		pass


	class Meta:
		db_table = 'labels'

	class Admin:
		list_display = ('name', 'kernel_config')

	def __str__(self):
		return self.name


class Host(dbmodels.Model, ModelExtensions):
	"""\
	Required:
	hostname

        optional:
        locked: host is locked and will not be queued

	Internal:
	synch_id: currently unused
	status: string describing status of host
	"""
	Status = enum.Enum('Verifying', 'Running', 'Ready', 'Repairing',
	                   'Repair Failed', 'Dead', string_values=True)

	hostname = dbmodels.CharField(maxlength=255, unique=True)
	labels = dbmodels.ManyToManyField(Label, blank=True,
					  filter_interface=dbmodels.HORIZONTAL)
	locked = dbmodels.BooleanField(default=False)
	synch_id = dbmodels.IntegerField(blank=True, null=True,
					 editable=settings.FULL_ADMIN)
	status = dbmodels.CharField(maxlength=255, default=Status.READY,
	                            choices=Status.choices(),
				    editable=settings.FULL_ADMIN)

	name_field = 'hostname'


	def save(self):
		# extra spaces in the hostname can be a sneaky source of errors
		self.hostname = self.hostname.strip()
		# is this a new object being saved for the first time?
		first_time = (self.id is None)
		super(Host, self).save()
		if first_time:
			everyone = AclGroup.objects.get(name='Everyone')
			everyone.hosts.add(self)


	def enqueue_job(self, job):
		' Enqueue a job on this host.'
		queue_entry = HostQueueEntry(host=self, job=job,
					     status=Job.Status.QUEUED,
					     priority=job.priority)
		# allow recovery of dead hosts from the frontend
		if not self.active_queue_entry() and self.is_dead():
			self.status = Host.Status.READY
			self.save()
		queue_entry.save()


	def block_auto_assign(self, job):
		'Block this host from being assigned to a job.'
		block = IneligibleHostQueue(job=job, host=self)
		block.save()


	def platform(self):
		# TODO(showard): slighly hacky?
		platforms = self.labels.filter(platform=True)
		if len(platforms) == 0:
			return None
		return platforms[0]
	platform.short_description = 'Platform'


	def is_dead(self):
		return self.status == Host.Status.REPAIR_FAILED


	def active_queue_entry(self):
		active = list(self.hostqueueentry_set.filter(active=True))
		if not active:
			return None
		assert len(active) == 1, ('More than one active entry for '
					  'host ' + self.hostname)
		return active[0]


	class Meta:
		db_table = 'hosts'

	class Admin:
		# TODO(showard) - showing platform requires a SQL query for
		# each row (since labels are many-to-many) - should we remove
		# it?
		list_display = ('hostname', 'platform', 'locked', 'status')
		list_filter = ('labels', 'locked')
		search_fields = ('hostname', 'status')

	def __str__(self):
		return self.hostname


class Test(dbmodels.Model, ModelExtensions):
	"""\
	Required:
	name: test name
	test_type: Client or Server
	path: path to pass to run_test()
	synch_type: whether the test should run synchronously or asynchronously

	Optional:
	test_class: used for categorization of tests
	description: arbirary text description
	"""
	Classes = enum.Enum('Kernel', 'Hardware', 'Canned Test Sets',
			    string_values=True)
	SynchType = enum.Enum('Asynchronous', 'Synchronous', start_value=1)
	# TODO(showard) - this should be merged with Job.ControlType (but right
	# now they use opposite values)
	Types = enum.Enum('Client', 'Server', start_value=1)

	name = dbmodels.CharField(maxlength=255, unique=True)
	test_class = dbmodels.CharField(maxlength=255,
					choices=Classes.choices())
	description = dbmodels.TextField(blank=True)
	test_type = dbmodels.SmallIntegerField(choices=Types.choices())
	synch_type = dbmodels.SmallIntegerField(choices=SynchType.choices(),
						default=SynchType.ASYNCHRONOUS)
	path = dbmodels.CharField(maxlength=255)

	name_field = 'name'


	class Meta:
		db_table = 'autotests'

	class Admin:
		fields = (
		    (None, {'fields' :
			    ('name', 'test_class', 'test_type', 'synch_type',
			     'path', 'description')}),
		    )
		list_display = ('name', 'test_type', 'synch_type',
				'description')
		search_fields = ('name',)

	def __str__(self):
		return self.name


class User(dbmodels.Model, ModelExtensions):
	"""\
	Required:
	login :user login name

	Optional:
	access_level: 0=User (default), 1=Admin, 100=Root
	"""
	ACCESS_ROOT = 100
	ACCESS_ADMIN = 1
	ACCESS_USER = 0

	login = dbmodels.CharField(maxlength=255, unique=True)
	access_level = dbmodels.IntegerField(default=ACCESS_USER, blank=True)

	name_field = 'login'


	def save(self):
		# is this a new object being saved for the first time?
		first_time = (self.id is None)
		super(User, self).save()
		if first_time:
			everyone = AclGroup.objects.get(name='Everyone')
			everyone.users.add(self)


	def has_access(self, target):
		if self.access_level >= self.ACCESS_ROOT:
			return True

		if isinstance(target, int):
			return self.access_level >= target
		if isinstance(target, Job):
			return (target.owner == self.login or
				self.access_level >= self.ACCESS_ADMIN)
		if isinstance(target, Host):
			acl_intersect = [group
					 for group in self.aclgroup_set.all()
					 if group in target.aclgroup_set.all()]
			return bool(acl_intersect)
		if isinstance(target, User):
			return self.access_level >= target.access_level
		raise ValueError('Invalid target type')


	class Meta:
		db_table = 'users'

	class Admin:
		list_display = ('login', 'access_level')
		search_fields = ('login',)

	def __str__(self):
		return self.login


class AclGroup(dbmodels.Model, ModelExtensions):
	"""\
	Required:
	name: name of ACL group

	Optional:
	description: arbitrary description of group
	"""
	name = dbmodels.CharField(maxlength=255, unique=True)
	description = dbmodels.CharField(maxlength=255, blank=True)
	users = dbmodels.ManyToManyField(User,
					 filter_interface=dbmodels.HORIZONTAL)
	hosts = dbmodels.ManyToManyField(Host,
					 filter_interface=dbmodels.HORIZONTAL)

	name_field = 'name'


	class Meta:
		db_table = 'acl_groups'

	class Admin:
		list_display = ('name', 'description')
		search_fields = ('name',)

	def __str__(self):
		return self.name

# hack to make the column name in the many-to-many DB tables match the one
# generated by ruby
AclGroup._meta.object_name = 'acl_group'


class JobManager(dbmodels.Manager):
	'Custom manager to provide efficient status counts querying.'
	def get_status_counts(self, job_ids):
		"""\
		Returns a dictionary mapping the given job IDs to their status
		count dictionaries.
		"""
		if not job_ids:
			return {}
		id_list = '(%s)' % ','.join(str(job_id) for job_id in job_ids)
		from django.db import connection
		cursor = connection.cursor()
		cursor.execute("""
		    SELECT job_id, status, COUNT(*)
		    FROM host_queue_entries
		    WHERE job_id IN %s
		    GROUP BY job_id, status
		    """ % id_list)
		all_job_counts = {}
		for job_id in job_ids:
			all_job_counts[job_id] = {}
		for job_id, status, count in cursor.fetchall():
			all_job_counts[job_id][status] = count
		return all_job_counts


class Job(dbmodels.Model, ModelExtensions):
	"""\
	owner: username of job owner
	name: job name (does not have to be unique)
	priority: Low, Medium, High, Urgent (or 0-3)
	control_file: contents of control file
	control_type: Client or Server
	created_on: date of job creation
	submitted_on: date of job submission
	synch_type: Asynchronous or Synchronous (i.e. job must run on all hosts
	            simultaneously; used for server-side control files)
	synch_count: ???
	synchronizing: for scheduler use
	"""
	Priority = enum.Enum('Low', 'Medium', 'High', 'Urgent')
	ControlType = enum.Enum('Server', 'Client', start_value=1)
	Status = enum.Enum('Created', 'Queued', 'Pending', 'Running',
			   'Completed', 'Abort', 'Aborting', 'Aborted',
			   'Failed', string_values=True)

	owner = dbmodels.CharField(maxlength=255)
	name = dbmodels.CharField(maxlength=255)
	priority = dbmodels.SmallIntegerField(choices=Priority.choices(),
					      blank=True, # to allow 0
					      default=Priority.MEDIUM)
	control_file = dbmodels.TextField()
	control_type = dbmodels.SmallIntegerField(choices=ControlType.choices(),
						  blank=True) # to allow 0
	created_on = dbmodels.DateTimeField(auto_now_add=True)
	synch_type = dbmodels.SmallIntegerField(
	    blank=True, null=True, choices=Test.SynchType.choices())
	synch_count = dbmodels.IntegerField(blank=True, null=True)
	synchronizing = dbmodels.BooleanField(default=False)


	# custom manager
	objects = JobManager()


	def is_server_job(self):
		return self.control_type == self.ControlType.SERVER


	@classmethod
	def create(cls, owner, name, priority, control_file, control_type,
		   hosts, synch_type):
		"""\
		Creates a job by taking some information (the listed args)
		and filling in the rest of the necessary information.
		"""
		job = cls.add_object(
		    owner=owner, name=name, priority=priority,
		    control_file=control_file, control_type=control_type,
		    synch_type=synch_type)

		if job.synch_type == Test.SynchType.SYNCHRONOUS:
			job.synch_count = len(hosts)
		else:
			if len(hosts) == 0:
				errors = {'hosts':
					  'asynchronous jobs require at least'
					  + ' one host to run on'}
				raise ValidationError(errors)
		job.save()
		return job


	def queue(self, hosts):
		'Enqueue a job on the given hosts.'
		for host in hosts:
			host.enqueue_job(self)
			host.block_auto_assign(self)


	def requeue(self, new_owner):
		'Creates a new job identical to this one'
		hosts = [queue_entry.meta_host or queue_entry.host
			 for queue_entry in self.hostqueueentry_set.all()]
		new_job = Job.create(
		    owner=new_owner, name=self.name, priority=self.priority,
		    control_file=self.control_file,
		    control_type=self.control_type, hosts=hosts,
		    synch_type=self.synch_type)
		new_job.queue(hosts)
		return new_job


	def abort(self):
		for queue_entry in self.hostqueueentry_set.all():
			if queue_entry.active:
				queue_entry.status = Job.Status.ABORT
			elif not queue_entry.complete:
				queue_entry.status = Job.Status.ABORTED
				queue_entry.active = False
				queue_entry.complete = True
			queue_entry.save()


	def user(self):
		try:
			return User.objects.get(login=self.owner)
		except self.DoesNotExist:
			return None


	class Meta:
		db_table = 'jobs'

	if settings.FULL_ADMIN:
		class Admin:
			list_display = ('id', 'owner', 'name', 'control_type')

	def __str__(self):
		return '%s (%s-%s)' % (self.name, self.id, self.owner)


class IneligibleHostQueue(dbmodels.Model):
	job = dbmodels.ForeignKey(Job)
	host = dbmodels.ForeignKey(Host)

	class Meta:
		db_table = 'ineligible_host_queues'

	if settings.FULL_ADMIN:
		class Admin:
			list_display = ('id', 'job', 'host')


class HostQueueEntry(dbmodels.Model, ModelExtensions):
	job = dbmodels.ForeignKey(Job)
	host = dbmodels.ForeignKey(Host, blank=True, null=True)
	priority = dbmodels.SmallIntegerField()
	status = dbmodels.CharField(maxlength=255)
	meta_host = dbmodels.ForeignKey(Label, blank=True, null=True,
					db_column='meta_host')
	active = dbmodels.BooleanField(default=False)
	complete = dbmodels.BooleanField(default=False)


	def is_meta_host_entry(self):
		'True if this is a entry has a meta_host instead of a host.'
		return self.host is None and self.meta_host is not None


	def save(self):
		if self.host:
			user = self.job.user()
			if user is None or not user.has_access(self.host):
				raise AclAccessViolation(
				    'User %s does not have permission to '
				    'access host %s' % (self.job.owner,
							self.host.hostname))
		super(HostQueueEntry, self).save()


	class Meta:
		db_table = 'host_queue_entries'

	if settings.FULL_ADMIN:
		class Admin:
			list_display = ('id', 'job', 'host', 'status',
					'meta_host')
