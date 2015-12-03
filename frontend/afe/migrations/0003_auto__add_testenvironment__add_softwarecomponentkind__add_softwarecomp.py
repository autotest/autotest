# -*- coding: utf-8 -*-
from django.db import models
from south.db import db
from south.v2 import SchemaMigration


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'TestEnvironment'
        db.create_table('test_environment', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('distro', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.LinuxDistro'])),
        ))
        db.send_create_signal('afe', ['TestEnvironment'])

        # Adding M2M table for field installed_software_components on 'TestEnvironment'
        m2m_table_name = 'test_environment_installed_software_components'
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('testenvironment', models.ForeignKey(orm['afe.testenvironment'], null=False)),
            ('softwarecomponent', models.ForeignKey(orm['afe.softwarecomponent'], null=False))
        ))
        db.create_unique(m2m_table_name, ['testenvironment_id', 'softwarecomponent_id'])

        # Adding model 'SoftwareComponentKind'
        db.create_table('software_component_kind', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=20)),
        ))
        db.send_create_signal('afe', ['SoftwareComponentKind'])

        # Adding model 'SoftwareComponent'
        db.create_table('software_component', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('kind', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.SoftwareComponentKind'], on_delete=models.PROTECT)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('version', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('release', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('checksum', self.gf('django.db.models.fields.CharField')(max_length=40)),
            ('arch', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.SoftwareComponentArch'], on_delete=models.PROTECT)),
        ))
        db.send_create_signal('afe', ['SoftwareComponent'])

        # Adding unique constraint on 'SoftwareComponent', fields ['kind', 'name', 'version', 'release', 'checksum', 'arch']
        db.create_unique('software_component', ['kind_id', 'name', 'version', 'release', 'checksum', 'arch_id'])

        # Adding model 'LinuxDistro'
        db.create_table('linux_distro', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=40)),
            ('version', self.gf('django.db.models.fields.CharField')(max_length=40)),
            ('release', self.gf('django.db.models.fields.CharField')(default='', max_length=40)),
            ('arch', self.gf('django.db.models.fields.CharField')(max_length=40)),
        ))
        db.send_create_signal('afe', ['LinuxDistro'])

        # Adding M2M table for field available_software_components on 'LinuxDistro'
        m2m_table_name = 'linux_distro_available_software_components'
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('linuxdistro', models.ForeignKey(orm['afe.linuxdistro'], null=False)),
            ('softwarecomponent', models.ForeignKey(orm['afe.softwarecomponent'], null=False))
        ))
        db.create_unique(m2m_table_name, ['linuxdistro_id', 'softwarecomponent_id'])

        # Adding unique constraint on 'LinuxDistro', fields ['name', 'version', 'release', 'arch']
        db.create_unique('linux_distro', ['name', 'version', 'release', 'arch'])

        # Adding model 'SoftwareComponentArch'
        db.create_table('software_component_arch', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=20)),
        ))
        db.send_create_signal('afe', ['SoftwareComponentArch'])

    def backwards(self, orm):
        # Removing unique constraint on 'LinuxDistro', fields ['name', 'version', 'release', 'arch']
        db.delete_unique('linux_distro', ['name', 'version', 'release', 'arch'])

        # Removing unique constraint on 'SoftwareComponent', fields ['kind', 'name', 'version', 'release', 'checksum', 'arch']
        db.delete_unique('software_component', ['kind_id', 'name', 'version', 'release', 'checksum', 'arch_id'])

        # Deleting model 'TestEnvironment'
        db.delete_table('test_environment')

        # Removing M2M table for field installed_software_components on 'TestEnvironment'
        db.delete_table('test_environment_installed_software_components')

        # Deleting model 'SoftwareComponentKind'
        db.delete_table('software_component_kind')

        # Deleting model 'SoftwareComponent'
        db.delete_table('software_component')

        # Deleting model 'LinuxDistro'
        db.delete_table('linux_distro')

        # Removing M2M table for field available_software_components on 'LinuxDistro'
        db.delete_table('linux_distro_available_software_components')

        # Deleting model 'SoftwareComponentArch'
        db.delete_table('software_component_arch')

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
            'reserve_hosts': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
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
        'afe.linuxdistro': {
            'Meta': {'unique_together': "(('name', 'version', 'release', 'arch'),)", 'object_name': 'LinuxDistro', 'db_table': "'linux_distro'"},
            'arch': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'available_software_components': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['afe.SoftwareComponent']", 'db_table': "'linux_distro_available_software_components'", 'symmetrical': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'release': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '40'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '40'})
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
        'afe.softwarecomponent': {
            'Meta': {'unique_together': "(('kind', 'name', 'version', 'release', 'checksum', 'arch'),)", 'object_name': 'SoftwareComponent', 'db_table': "'software_component'"},
            'arch': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.SoftwareComponentArch']", 'on_delete': 'models.PROTECT'}),
            'checksum': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'kind': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.SoftwareComponentKind']", 'on_delete': 'models.PROTECT'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'release': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'afe.softwarecomponentarch': {
            'Meta': {'object_name': 'SoftwareComponentArch', 'db_table': "'software_component_arch'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '20'})
        },
        'afe.softwarecomponentkind': {
            'Meta': {'object_name': 'SoftwareComponentKind', 'db_table': "'software_component_kind'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '20'})
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
        'afe.testenvironment': {
            'Meta': {'object_name': 'TestEnvironment', 'db_table': "'test_environment'"},
            'distro': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.LinuxDistro']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'installed_software_components': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['afe.SoftwareComponent']", 'db_table': "'test_environment_installed_software_components'", 'symmetrical': 'False'})
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
