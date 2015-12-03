# -*- coding: utf-8 -*-
from south.db import db
from south.v2 import SchemaMigration


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Test.test_environment'
        db.add_column('tko_tests', 'test_environment',
                      self.gf('django.db.models.fields.related.ForeignKey')(to=orm['afe.TestEnvironment'], null=True),
                      keep_default=False)

    def backwards(self, orm):
        # Deleting field 'Test.test_environment'
        db.delete_column('tko_tests', 'test_environment_id')

    models = {
        'afe.linuxdistro': {
            'Meta': {'unique_together': "(('name', 'major', 'minor', 'arch'),)", 'object_name': 'LinuxDistro', 'db_table': "'linux_distro'"},
            'arch': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'major': ('django.db.models.fields.IntegerField', [], {}),
            'minor': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'software_components': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['afe.SoftwareComponent']", 'db_table': "'linux_distro_software_components'", 'symmetrical': 'False'})
        },
        'afe.softwarecomponent': {
            'Meta': {'unique_together': "(('kind', 'name', 'version', 'release', 'checksum', 'arch'),)", 'object_name': 'SoftwareComponent', 'db_table': "'software_component'"},
            'arch': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.SoftwareComponentArch']", 'on_delete': 'models.PROTECT'}),
            'checksum': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'kind': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.SoftwareComponentKind']", 'on_delete': 'models.PROTECT'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'release': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '40'})
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
        'afe.testenvironment': {
            'Meta': {'object_name': 'TestEnvironment', 'db_table': "'test_environment'"},
            'distro': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.LinuxDistro']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'software_components': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['afe.SoftwareComponent']", 'db_table': "'test_environment_software_components'", 'symmetrical': 'False'})
        },
        'tko.embeddedgraphingquery': {
            'Meta': {'object_name': 'EmbeddedGraphingQuery', 'db_table': "'tko_embedded_graphing_queries'"},
            'cached_png': ('django.db.models.fields.TextField', [], {}),
            'graph_type': ('django.db.models.fields.CharField', [], {'max_length': '16'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_updated': ('django.db.models.fields.DateTimeField', [], {}),
            'params': ('django.db.models.fields.TextField', [], {}),
            'refresh_time': ('django.db.models.fields.DateTimeField', [], {}),
            'url_token': ('django.db.models.fields.TextField', [], {})
        },
        'tko.iterationattribute': {
            'Meta': {'object_name': 'IterationAttribute', 'db_table': "'tko_iteration_attributes'"},
            'attribute': ('django.db.models.fields.CharField', [], {'max_length': '90'}),
            'iteration': ('django.db.models.fields.IntegerField', [], {}),
            'test': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['tko.Test']", 'primary_key': 'True', 'db_column': "'test_idx'"}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'})
        },
        'tko.iterationresult': {
            'Meta': {'object_name': 'IterationResult', 'db_table': "'tko_iteration_result'"},
            'attribute': ('django.db.models.fields.CharField', [], {'max_length': '90'}),
            'iteration': ('django.db.models.fields.IntegerField', [], {}),
            'test': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['tko.Test']", 'primary_key': 'True', 'db_column': "'test_idx'"}),
            'value': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'})
        },
        'tko.job': {
            'Meta': {'object_name': 'Job', 'db_table': "'tko_jobs'"},
            'afe_job_id': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True'}),
            'finished_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'job_idx': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'label': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
            'machine': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['tko.Machine']", 'db_column': "'machine_idx'"}),
            'queued_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'started_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'tag': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '240'})
        },
        'tko.jobkeyval': {
            'Meta': {'object_name': 'JobKeyval', 'db_table': "'tko_job_keyvals'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'job': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['tko.Job']"}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '90'}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'})
        },
        'tko.kernel': {
            'Meta': {'object_name': 'Kernel', 'db_table': "'tko_kernels'"},
            'base': ('django.db.models.fields.CharField', [], {'max_length': '90'}),
            'kernel_hash': ('django.db.models.fields.CharField', [], {'max_length': '105'}),
            'kernel_idx': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'printable': ('django.db.models.fields.CharField', [], {'max_length': '300'})
        },
        'tko.machine': {
            'Meta': {'object_name': 'Machine', 'db_table': "'tko_machines'"},
            'hostname': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'machine_group': ('django.db.models.fields.CharField', [], {'max_length': '240', 'blank': 'True'}),
            'machine_idx': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'owner': ('django.db.models.fields.CharField', [], {'max_length': '240', 'blank': 'True'})
        },
        'tko.patch': {
            'Meta': {'object_name': 'Patch', 'db_table': "'tko_patches'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'kernel': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['tko.Kernel']", 'db_column': "'kernel_idx'"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '240', 'blank': 'True'}),
            'the_hash': ('django.db.models.fields.CharField', [], {'max_length': '105', 'db_column': "'hash'", 'blank': 'True'}),
            'url': ('django.db.models.fields.CharField', [], {'max_length': '900', 'blank': 'True'})
        },
        'tko.savedquery': {
            'Meta': {'object_name': 'SavedQuery', 'db_table': "'tko_saved_queries'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'owner': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'url_token': ('django.db.models.fields.TextField', [], {})
        },
        'tko.status': {
            'Meta': {'object_name': 'Status'},
            'status_idx': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'word': ('django.db.models.fields.CharField', [], {'max_length': '30'})
        },
        'tko.test': {
            'Meta': {'object_name': 'Test', 'db_table': "'tko_tests'"},
            'finished_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'job': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['tko.Job']", 'db_column': "'job_idx'"}),
            'kernel': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['tko.Kernel']", 'db_column': "'kernel_idx'"}),
            'machine': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['tko.Machine']", 'db_column': "'machine_idx'"}),
            'reason': ('django.db.models.fields.CharField', [], {'max_length': '3072', 'blank': 'True'}),
            'started_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['tko.Status']", 'db_column': "'status'"}),
            'subdir': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'}),
            'test': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
            'test_environment': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['afe.TestEnvironment']", 'null': 'True'}),
            'test_idx': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'tko.testattribute': {
            'Meta': {'object_name': 'TestAttribute', 'db_table': "'tko_test_attributes'"},
            'attribute': ('django.db.models.fields.CharField', [], {'max_length': '90'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'test': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['tko.Test']", 'db_column': "'test_idx'"}),
            'user_created': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'})
        },
        'tko.testlabel': {
            'Meta': {'object_name': 'TestLabel', 'db_table': "'tko_test_labels'"},
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'tests': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['tko.Test']", 'symmetrical': 'False', 'db_table': "'tko_test_labels_tests'", 'blank': 'True'})
        },
        'tko.testview': {
            'Meta': {'object_name': 'TestView', 'db_table': "'tko_test_view_2'", 'managed': 'False'},
            'afe_job_id': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'hostname': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'}),
            'job_finished_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'job_idx': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'job_name': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'}),
            'job_owner': ('django.db.models.fields.CharField', [], {'max_length': '240', 'blank': 'True'}),
            'job_queued_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'job_started_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'job_tag': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'}),
            'kernel': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'}),
            'kernel_base': ('django.db.models.fields.CharField', [], {'max_length': '90', 'blank': 'True'}),
            'kernel_hash': ('django.db.models.fields.CharField', [], {'max_length': '105', 'blank': 'True'}),
            'kernel_idx': ('django.db.models.fields.IntegerField', [], {}),
            'machine_idx': ('django.db.models.fields.IntegerField', [], {}),
            'machine_owner': ('django.db.models.fields.CharField', [], {'max_length': '240', 'blank': 'True'}),
            'platform': ('django.db.models.fields.CharField', [], {'max_length': '240', 'blank': 'True'}),
            'reason': ('django.db.models.fields.CharField', [], {'max_length': '3072', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'status_idx': ('django.db.models.fields.IntegerField', [], {}),
            'subdir': ('django.db.models.fields.CharField', [], {'max_length': '180', 'blank': 'True'}),
            'test_finished_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'test_idx': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'test_name': ('django.db.models.fields.CharField', [], {'max_length': '90', 'blank': 'True'}),
            'test_started_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['tko']
