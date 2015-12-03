# -*- coding: utf-8 -*-
from django.db import models
from south.db import db
from south.v2 import SchemaMigration


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'AtomicGroup'
        db.create_table('afe_atomic_groups', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255)),
            ('description', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('max_number_of_machines', self.gf('django.db.models.fields.IntegerField')(default=333333333)),
            ('invalid', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('afe', ['AtomicGroup'])

        # Adding model 'Label'
        db.create_table('afe_labels', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255)),
            ('kernel_config', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('platform', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('invalid', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('only_if_needed', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('atomic_group', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.AtomicGroup'], null=True, blank=True)),
        ))
        db.send_create_signal('afe', ['Label'])

        # Adding model 'Drone'
        db.create_table('afe_drones', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('hostname', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255)),
        ))
        db.send_create_signal('afe', ['Drone'])

        # Adding model 'DroneSet'
        db.create_table('afe_drone_sets', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255)),
        ))
        db.send_create_signal('afe', ['DroneSet'])

        # Adding M2M table for field drones on 'DroneSet'
        db.create_table('afe_drone_sets_drones', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('droneset', models.ForeignKey(orm['afe.droneset'], null=False)),
            ('drone', models.ForeignKey(orm['afe.drone'], null=False))
        ))
        db.create_unique('afe_drone_sets_drones', ['droneset_id', 'drone_id'])

        # Adding model 'User'
        db.create_table('afe_users', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('login', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255)),
            ('access_level', self.gf('django.db.models.fields.IntegerField')(default=0, blank=True)),
            ('reboot_before', self.gf('django.db.models.fields.SmallIntegerField')(default=1, blank=True)),
            ('reboot_after', self.gf('django.db.models.fields.SmallIntegerField')(default=2, blank=True)),
            ('drone_set', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.DroneSet'], null=True, blank=True)),
            ('show_experimental', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('afe', ['User'])

        # Adding model 'Host'
        db.create_table('afe_hosts', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('hostname', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255)),
            ('locked', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('synch_id', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('status', self.gf('django.db.models.fields.CharField')(default='Ready', max_length=255)),
            ('invalid', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('protection', self.gf('django.db.models.fields.SmallIntegerField')(default=0, blank=True)),
            ('locked_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.User'], null=True, blank=True)),
            ('lock_time', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('dirty', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal('afe', ['Host'])

        # Adding M2M table for field labels on 'Host'
        db.create_table('afe_hosts_labels', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('host', models.ForeignKey(orm['afe.host'], null=False)),
            ('label', models.ForeignKey(orm['afe.label'], null=False))
        ))
        db.create_unique('afe_hosts_labels', ['host_id', 'label_id'])

        # Adding model 'HostAttribute'
        db.create_table('afe_host_attributes', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('host', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.Host'])),
            ('attribute', self.gf('django.db.models.fields.CharField')(max_length=90)),
            ('value', self.gf('django.db.models.fields.CharField')(max_length=300)),
        ))
        db.send_create_signal('afe', ['HostAttribute'])

        # Adding model 'Test'
        db.create_table('afe_autotests', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255)),
            ('author', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('test_class', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('test_category', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('dependencies', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('description', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('experimental', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('run_verify', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('test_time', self.gf('django.db.models.fields.SmallIntegerField')(default=2)),
            ('test_type', self.gf('django.db.models.fields.SmallIntegerField')(default=1)),
            ('sync_count', self.gf('django.db.models.fields.PositiveIntegerField')(default=1)),
            ('path', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255)),
        ))
        db.send_create_signal('afe', ['Test'])

        # Adding M2M table for field dependency_labels on 'Test'
        db.create_table('afe_autotests_dependency_labels', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('test', models.ForeignKey(orm['afe.test'], null=False)),
            ('label', models.ForeignKey(orm['afe.label'], null=False))
        ))
        db.create_unique('afe_autotests_dependency_labels', ['test_id', 'label_id'])

        # Adding model 'TestParameter'
        db.create_table('afe_test_parameters', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('test', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.Test'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal('afe', ['TestParameter'])

        # Adding unique constraint on 'TestParameter', fields ['test', 'name']
        db.create_unique('afe_test_parameters', ['test_id', 'name'])

        # Adding model 'Profiler'
        db.create_table('afe_profilers', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255)),
            ('description', self.gf('django.db.models.fields.TextField')(blank=True)),
        ))
        db.send_create_signal('afe', ['Profiler'])

        # Adding model 'AclGroup'
        db.create_table('afe_acl_groups', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255)),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
        ))
        db.send_create_signal('afe', ['AclGroup'])

        # Adding M2M table for field users on 'AclGroup'
        db.create_table('afe_acl_groups_users', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('aclgroup', models.ForeignKey(orm['afe.aclgroup'], null=False)),
            ('user', models.ForeignKey(orm['afe.user'], null=False))
        ))
        db.create_unique('afe_acl_groups_users', ['aclgroup_id', 'user_id'])

        # Adding M2M table for field hosts on 'AclGroup'
        db.create_table('afe_acl_groups_hosts', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('aclgroup', models.ForeignKey(orm['afe.aclgroup'], null=False)),
            ('host', models.ForeignKey(orm['afe.host'], null=False))
        ))
        db.create_unique('afe_acl_groups_hosts', ['aclgroup_id', 'host_id'])

        # Adding model 'Kernel'
        db.create_table('afe_kernels', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('version', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('cmdline', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
        ))
        db.send_create_signal('afe', ['Kernel'])

        # Adding unique constraint on 'Kernel', fields ['version', 'cmdline']
        db.create_unique('afe_kernels', ['version', 'cmdline'])

        # Adding model 'ParameterizedJob'
        db.create_table('afe_parameterized_jobs', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('test', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.Test'])),
            ('label', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.Label'], null=True)),
            ('use_container', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('profile_only', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('upload_kernel_config', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('afe', ['ParameterizedJob'])

        # Adding M2M table for field kernels on 'ParameterizedJob'
        db.create_table('afe_parameterized_job_kernels', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('parameterizedjob', models.ForeignKey(orm['afe.parameterizedjob'], null=False)),
            ('kernel', models.ForeignKey(orm['afe.kernel'], null=False))
        ))
        db.create_unique('afe_parameterized_job_kernels', ['parameterizedjob_id', 'kernel_id'])

        # Adding model 'ParameterizedJobProfiler'
        db.create_table('afe_parameterized_jobs_profilers', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('parameterized_job', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.ParameterizedJob'])),
            ('profiler', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.Profiler'])),
        ))
        db.send_create_signal('afe', ['ParameterizedJobProfiler'])

        # Adding unique constraint on 'ParameterizedJobProfiler', fields ['parameterized_job', 'profiler']
        db.create_unique('afe_parameterized_jobs_profilers', ['parameterized_job_id', 'profiler_id'])

        # Adding model 'ParameterizedJobProfilerParameter'
        db.create_table('afe_parameterized_job_profiler_parameters', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('parameterized_job_profiler', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.ParameterizedJobProfiler'])),
            ('parameter_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('parameter_value', self.gf('django.db.models.fields.TextField')()),
            ('parameter_type', self.gf('django.db.models.fields.CharField')(max_length=8)),
        ))
        db.send_create_signal('afe', ['ParameterizedJobProfilerParameter'])

        # Adding unique constraint on 'ParameterizedJobProfilerParameter', fields ['parameterized_job_profiler', 'parameter_name']
        db.create_unique('afe_parameterized_job_profiler_parameters', ['parameterized_job_profiler_id', 'parameter_name'])

        # Adding model 'ParameterizedJobParameter'
        db.create_table('afe_parameterized_job_parameters', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('parameterized_job', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.ParameterizedJob'])),
            ('test_parameter', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.TestParameter'])),
            ('parameter_value', self.gf('django.db.models.fields.TextField')()),
            ('parameter_type', self.gf('django.db.models.fields.CharField')(max_length=8)),
        ))
        db.send_create_signal('afe', ['ParameterizedJobParameter'])

        # Adding unique constraint on 'ParameterizedJobParameter', fields ['parameterized_job', 'test_parameter']
        db.create_unique('afe_parameterized_job_parameters', ['parameterized_job_id', 'test_parameter_id'])

        # Adding model 'Job'
        db.create_table('afe_jobs', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('owner', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('priority', self.gf('django.db.models.fields.SmallIntegerField')(default=1, blank=True)),
            ('control_file', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('control_type', self.gf('django.db.models.fields.SmallIntegerField')(default=2, blank=True)),
            ('created_on', self.gf('django.db.models.fields.DateTimeField')()),
            ('synch_count', self.gf('django.db.models.fields.IntegerField')(default=1, null=True)),
            ('timeout', self.gf('django.db.models.fields.IntegerField')(default='72')),
            ('run_verify', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('email_list', self.gf('django.db.models.fields.CharField')(max_length=250, blank=True)),
            ('reboot_before', self.gf('django.db.models.fields.SmallIntegerField')(default=1, blank=True)),
            ('reboot_after', self.gf('django.db.models.fields.SmallIntegerField')(default=2, blank=True)),
            ('parse_failed_repair', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('max_runtime_hrs', self.gf('django.db.models.fields.IntegerField')(default='72')),
            ('drone_set', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.DroneSet'], null=True, blank=True)),
            ('parameterized_job', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.ParameterizedJob'], null=True, blank=True)),
        ))
        db.send_create_signal('afe', ['Job'])

        # Adding M2M table for field dependency_labels on 'Job'
        db.create_table('afe_jobs_dependency_labels', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('job', models.ForeignKey(orm['afe.job'], null=False)),
            ('label', models.ForeignKey(orm['afe.label'], null=False))
        ))
        db.create_unique('afe_jobs_dependency_labels', ['job_id', 'label_id'])

        # Adding model 'JobKeyval'
        db.create_table('afe_job_keyvals', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('job', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.Job'])),
            ('key', self.gf('django.db.models.fields.CharField')(max_length=90)),
            ('value', self.gf('django.db.models.fields.CharField')(max_length=300)),
        ))
        db.send_create_signal('afe', ['JobKeyval'])

        # Adding model 'IneligibleHostQueue'
        db.create_table('afe_ineligible_host_queues', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('job', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.Job'])),
            ('host', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.Host'])),
        ))
        db.send_create_signal('afe', ['IneligibleHostQueue'])

        # Adding model 'HostQueueEntry'
        db.create_table('afe_host_queue_entries', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('job', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.Job'])),
            ('host', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.Host'], null=True, blank=True)),
            ('profile', self.gf('django.db.models.fields.CharField')(default='', max_length=255, blank=True)),
            ('status', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('meta_host', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.Label'], null=True, db_column='meta_host', blank=True)),
            ('active', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('complete', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('execution_subdir', self.gf('django.db.models.fields.CharField')(default='', max_length=255, blank=True)),
            ('atomic_group', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.AtomicGroup'], null=True, blank=True)),
            ('aborted', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('started_on', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal('afe', ['HostQueueEntry'])

        # Adding model 'AbortedHostQueueEntry'
        db.create_table('afe_aborted_host_queue_entries', (
            ('queue_entry', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['afe.HostQueueEntry'], unique=True, primary_key=True)),
            ('aborted_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.User'])),
            ('aborted_on', self.gf('django.db.models.fields.DateTimeField')()),
        ))
        db.send_create_signal('afe', ['AbortedHostQueueEntry'])

        # Adding model 'RecurringRun'
        db.create_table('afe_recurring_run', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('job', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.Job'])),
            ('owner', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.User'])),
            ('start_date', self.gf('django.db.models.fields.DateTimeField')()),
            ('loop_period', self.gf('django.db.models.fields.IntegerField')(blank=True)),
            ('loop_count', self.gf('django.db.models.fields.IntegerField')(blank=True)),
        ))
        db.send_create_signal('afe', ['RecurringRun'])

        # Adding model 'SpecialTask'
        db.create_table('afe_special_tasks', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('host', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.Host'])),
            ('task', self.gf('django.db.models.fields.CharField')(max_length=64)),
            ('requested_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.User'])),
            ('time_requested', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_complete', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('time_started', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('queue_entry', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.HostQueueEntry'], null=True, blank=True)),
            ('success', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('afe', ['SpecialTask'])

        # Adding model 'MigrateInfo'
        db.create_table('migrate_info', (
            ('version', self.gf('django.db.models.fields.IntegerField')(default=None, primary_key=True)),
        ))
        db.send_create_signal('afe', ['MigrateInfo'])

    def backwards(self, orm):
        # Removing unique constraint on 'ParameterizedJobParameter', fields ['parameterized_job', 'test_parameter']
        db.delete_unique('afe_parameterized_job_parameters', ['parameterized_job_id', 'test_parameter_id'])

        # Removing unique constraint on 'ParameterizedJobProfilerParameter', fields ['parameterized_job_profiler', 'parameter_name']
        db.delete_unique('afe_parameterized_job_profiler_parameters', ['parameterized_job_profiler_id', 'parameter_name'])

        # Removing unique constraint on 'ParameterizedJobProfiler', fields ['parameterized_job', 'profiler']
        db.delete_unique('afe_parameterized_jobs_profilers', ['parameterized_job_id', 'profiler_id'])

        # Removing unique constraint on 'Kernel', fields ['version', 'cmdline']
        db.delete_unique('afe_kernels', ['version', 'cmdline'])

        # Removing unique constraint on 'TestParameter', fields ['test', 'name']
        db.delete_unique('afe_test_parameters', ['test_id', 'name'])

        # Deleting model 'AtomicGroup'
        db.delete_table('afe_atomic_groups')

        # Deleting model 'Label'
        db.delete_table('afe_labels')

        # Deleting model 'Drone'
        db.delete_table('afe_drones')

        # Deleting model 'DroneSet'
        db.delete_table('afe_drone_sets')

        # Removing M2M table for field drones on 'DroneSet'
        db.delete_table('afe_drone_sets_drones')

        # Deleting model 'User'
        db.delete_table('afe_users')

        # Deleting model 'Host'
        db.delete_table('afe_hosts')

        # Removing M2M table for field labels on 'Host'
        db.delete_table('afe_hosts_labels')

        # Deleting model 'HostAttribute'
        db.delete_table('afe_host_attributes')

        # Deleting model 'Test'
        db.delete_table('afe_autotests')

        # Removing M2M table for field dependency_labels on 'Test'
        db.delete_table('afe_autotests_dependency_labels')

        # Deleting model 'TestParameter'
        db.delete_table('afe_test_parameters')

        # Deleting model 'Profiler'
        db.delete_table('afe_profilers')

        # Deleting model 'AclGroup'
        db.delete_table('afe_acl_groups')

        # Removing M2M table for field users on 'AclGroup'
        db.delete_table('afe_acl_groups_users')

        # Removing M2M table for field hosts on 'AclGroup'
        db.delete_table('afe_acl_groups_hosts')

        # Deleting model 'Kernel'
        db.delete_table('afe_kernels')

        # Deleting model 'ParameterizedJob'
        db.delete_table('afe_parameterized_jobs')

        # Removing M2M table for field kernels on 'ParameterizedJob'
        db.delete_table('afe_parameterized_job_kernels')

        # Deleting model 'ParameterizedJobProfiler'
        db.delete_table('afe_parameterized_jobs_profilers')

        # Deleting model 'ParameterizedJobProfilerParameter'
        db.delete_table('afe_parameterized_job_profiler_parameters')

        # Deleting model 'ParameterizedJobParameter'
        db.delete_table('afe_parameterized_job_parameters')

        # Deleting model 'Job'
        db.delete_table('afe_jobs')

        # Removing M2M table for field dependency_labels on 'Job'
        db.delete_table('afe_jobs_dependency_labels')

        # Deleting model 'JobKeyval'
        db.delete_table('afe_job_keyvals')

        # Deleting model 'IneligibleHostQueue'
        db.delete_table('afe_ineligible_host_queues')

        # Deleting model 'HostQueueEntry'
        db.delete_table('afe_host_queue_entries')

        # Deleting model 'AbortedHostQueueEntry'
        db.delete_table('afe_aborted_host_queue_entries')

        # Deleting model 'RecurringRun'
        db.delete_table('afe_recurring_run')

        # Deleting model 'SpecialTask'
        db.delete_table('afe_special_tasks')

        # Deleting model 'MigrateInfo'
        db.delete_table('migrate_info')

    models = {
        'afe.abortedhostqueueentry': {
            'Meta': {'object_name': 'AbortedHostQueueEntry', 'db_table': "'afe_aborted_host_queue_entries'"},
            'aborted_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.User']"}),
            'aborted_on': ('django.db.models.fields.DateTimeField', [], {}),
            'queue_entry': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['afe.HostQueueEntry']", 'unique': 'True', 'primary_key': 'True'})
        },
        'afe.aclgroup': {
            'Meta': {'object_name': 'AclGroup', 'db_table': "'afe_acl_groups'"},
            'description': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'hosts': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['afe.Host']", 'symmetrical': 'False', 'db_table': "'afe_acl_groups_hosts'", 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'users': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['afe.User']", 'db_table': "'afe_acl_groups_users'", 'symmetrical': 'False'})
        },
        'afe.atomicgroup': {
            'Meta': {'object_name': 'AtomicGroup', 'db_table': "'afe_atomic_groups'"},
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invalid': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'max_number_of_machines': ('django.db.models.fields.IntegerField', [], {'default': '333333333'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'})
        },
        'afe.drone': {
            'Meta': {'object_name': 'Drone', 'db_table': "'afe_drones'"},
            'hostname': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'afe.droneset': {
            'Meta': {'object_name': 'DroneSet', 'db_table': "'afe_drone_sets'"},
            'drones': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['afe.Drone']", 'db_table': "'afe_drone_sets_drones'", 'symmetrical': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'})
        },
        'afe.host': {
            'Meta': {'object_name': 'Host', 'db_table': "'afe_hosts'"},
            'dirty': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'hostname': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invalid': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'labels': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['afe.Label']", 'symmetrical': 'False', 'db_table': "'afe_hosts_labels'", 'blank': 'True'}),
            'lock_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'locked': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'locked_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.User']", 'null': 'True', 'blank': 'True'}),
            'protection': ('django.db.models.fields.SmallIntegerField', [], {'default': '0', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'Ready'", 'max_length': '255'}),
            'synch_id': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'})
        },
        'afe.hostattribute': {
            'Meta': {'object_name': 'HostAttribute', 'db_table': "'afe_host_attributes'"},
            'attribute': ('django.db.models.fields.CharField', [], {'max_length': '90'}),
            'host': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.Host']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '300'})
        },
        'afe.hostqueueentry': {
            'Meta': {'object_name': 'HostQueueEntry', 'db_table': "'afe_host_queue_entries'"},
            'aborted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'atomic_group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.AtomicGroup']", 'null': 'True', 'blank': 'True'}),
            'complete': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'execution_subdir': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'host': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.Host']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'job': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.Job']"}),
            'meta_host': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.Label']", 'null': 'True', 'db_column': "'meta_host'", 'blank': 'True'}),
            'profile': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'started_on': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'afe.ineligiblehostqueue': {
            'Meta': {'object_name': 'IneligibleHostQueue', 'db_table': "'afe_ineligible_host_queues'"},
            'host': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.Host']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'job': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.Job']"})
        },
        'afe.job': {
            'Meta': {'object_name': 'Job', 'db_table': "'afe_jobs'"},
            'control_file': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'control_type': ('django.db.models.fields.SmallIntegerField', [], {'default': '2', 'blank': 'True'}),
            'created_on': ('django.db.models.fields.DateTimeField', [], {}),
            'dependency_labels': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['afe.Label']", 'symmetrical': 'False', 'db_table': "'afe_jobs_dependency_labels'", 'blank': 'True'}),
            'drone_set': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.DroneSet']", 'null': 'True', 'blank': 'True'}),
            'email_list': ('django.db.models.fields.CharField', [], {'max_length': '250', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'max_runtime_hrs': ('django.db.models.fields.IntegerField', [], {'default': "'72'"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'owner': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'parameterized_job': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.ParameterizedJob']", 'null': 'True', 'blank': 'True'}),
            'parse_failed_repair': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'priority': ('django.db.models.fields.SmallIntegerField', [], {'default': '1', 'blank': 'True'}),
            'reboot_after': ('django.db.models.fields.SmallIntegerField', [], {'default': '2', 'blank': 'True'}),
            'reboot_before': ('django.db.models.fields.SmallIntegerField', [], {'default': '1', 'blank': 'True'}),
            'run_verify': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'synch_count': ('django.db.models.fields.IntegerField', [], {'default': '1', 'null': 'True'}),
            'timeout': ('django.db.models.fields.IntegerField', [], {'default': "'72'"})
        },
        'afe.jobkeyval': {
            'Meta': {'object_name': 'JobKeyval', 'db_table': "'afe_job_keyvals'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'job': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.Job']"}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '90'}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '300'})
        },
        'afe.kernel': {
            'Meta': {'unique_together': "(('version', 'cmdline'),)", 'object_name': 'Kernel', 'db_table': "'afe_kernels'"},
            'cmdline': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'afe.label': {
            'Meta': {'object_name': 'Label', 'db_table': "'afe_labels'"},
            'atomic_group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.AtomicGroup']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invalid': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'kernel_config': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'only_if_needed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'platform': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'afe.migrateinfo': {
            'Meta': {'object_name': 'MigrateInfo', 'db_table': "'migrate_info'"},
            'version': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'primary_key': 'True'})
        },
        'afe.parameterizedjob': {
            'Meta': {'object_name': 'ParameterizedJob', 'db_table': "'afe_parameterized_jobs'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'kernels': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['afe.Kernel']", 'db_table': "'afe_parameterized_job_kernels'", 'symmetrical': 'False'}),
            'label': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.Label']", 'null': 'True'}),
            'profile_only': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'profilers': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['afe.Profiler']", 'through': "orm['afe.ParameterizedJobProfiler']", 'symmetrical': 'False'}),
            'test': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.Test']"}),
            'upload_kernel_config': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'use_container': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'afe.parameterizedjobparameter': {
            'Meta': {'unique_together': "(('parameterized_job', 'test_parameter'),)", 'object_name': 'ParameterizedJobParameter', 'db_table': "'afe_parameterized_job_parameters'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'parameter_type': ('django.db.models.fields.CharField', [], {'max_length': '8'}),
            'parameter_value': ('django.db.models.fields.TextField', [], {}),
            'parameterized_job': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.ParameterizedJob']"}),
            'test_parameter': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.TestParameter']"})
        },
        'afe.parameterizedjobprofiler': {
            'Meta': {'unique_together': "(('parameterized_job', 'profiler'),)", 'object_name': 'ParameterizedJobProfiler', 'db_table': "'afe_parameterized_jobs_profilers'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'parameterized_job': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.ParameterizedJob']"}),
            'profiler': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.Profiler']"})
        },
        'afe.parameterizedjobprofilerparameter': {
            'Meta': {'unique_together': "(('parameterized_job_profiler', 'parameter_name'),)", 'object_name': 'ParameterizedJobProfilerParameter', 'db_table': "'afe_parameterized_job_profiler_parameters'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'parameter_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'parameter_type': ('django.db.models.fields.CharField', [], {'max_length': '8'}),
            'parameter_value': ('django.db.models.fields.TextField', [], {}),
            'parameterized_job_profiler': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.ParameterizedJobProfiler']"})
        },
        'afe.profiler': {
            'Meta': {'object_name': 'Profiler', 'db_table': "'afe_profilers'"},
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'})
        },
        'afe.recurringrun': {
            'Meta': {'object_name': 'RecurringRun', 'db_table': "'afe_recurring_run'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'job': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.Job']"}),
            'loop_count': ('django.db.models.fields.IntegerField', [], {'blank': 'True'}),
            'loop_period': ('django.db.models.fields.IntegerField', [], {'blank': 'True'}),
            'owner': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.User']"}),
            'start_date': ('django.db.models.fields.DateTimeField', [], {})
        },
        'afe.specialtask': {
            'Meta': {'object_name': 'SpecialTask', 'db_table': "'afe_special_tasks'"},
            'host': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.Host']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_complete': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'queue_entry': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.HostQueueEntry']", 'null': 'True', 'blank': 'True'}),
            'requested_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.User']"}),
            'success': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'task': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'time_requested': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'time_started': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        },
        'afe.test': {
            'Meta': {'object_name': 'Test', 'db_table': "'afe_autotests'"},
            'author': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'dependencies': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'dependency_labels': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['afe.Label']", 'symmetrical': 'False', 'db_table': "'afe_autotests_dependency_labels'", 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'experimental': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'path': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'run_verify': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'sync_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '1'}),
            'test_category': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'test_class': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'test_time': ('django.db.models.fields.SmallIntegerField', [], {'default': '2'}),
            'test_type': ('django.db.models.fields.SmallIntegerField', [], {'default': '1'})
        },
        'afe.testparameter': {
            'Meta': {'unique_together': "(('test', 'name'),)", 'object_name': 'TestParameter', 'db_table': "'afe_test_parameters'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'test': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.Test']"})
        },
        'afe.user': {
            'Meta': {'object_name': 'User', 'db_table': "'afe_users'"},
            'access_level': ('django.db.models.fields.IntegerField', [], {'default': '0', 'blank': 'True'}),
            'drone_set': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.DroneSet']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'login': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'reboot_after': ('django.db.models.fields.SmallIntegerField', [], {'default': '2', 'blank': 'True'}),
            'reboot_before': ('django.db.models.fields.SmallIntegerField', [], {'default': '1', 'blank': 'True'}),
            'show_experimental': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        }
    }

    complete_apps = ['afe']
