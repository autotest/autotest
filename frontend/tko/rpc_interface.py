import os
import pickle
import datetime
import itertools
import operator
from django.db import models as dbmodels
from autotest.frontend.afe import rpc_utils, model_logic
from autotest.frontend.afe import models as afe_models, readonly_connection
from autotest.frontend.tko import models, tko_rpc_utils, graphing_utils
from autotest.frontend.tko import preconfigs


#
# IMPORTANT: please update INTERFACE_VERSION with the current date whenever
# the interface changes, so that RPC clients can handle the changes
#
INTERFACE_VERSION = (2013, 05, 23)


# table/spreadsheet view support

def get_test_views(**filter_data):
    return rpc_utils.prepare_for_serialization(
        models.TestView.list_objects(filter_data))


def get_num_test_views(**filter_data):
    return models.TestView.query_count(filter_data)


def get_group_counts(group_by, header_groups=None, fixed_headers=None,
                     extra_select_fields=None, **filter_data):
    """
    Queries against TestView grouping by the specified fields and computings
    counts for each group.
    * group_by should be a list of field names.
    * extra_select_fields can be used to specify additional fields to select
      (usually for aggregate functions).
    * header_groups can be used to get lists of unique combinations of group
      fields.  It should be a list of tuples of fields from group_by.  It's
      primarily for use by the spreadsheet view.
    * fixed_headers can map header fields to lists of values.  the header will
      guaranteed to return exactly those value.  this does not work together
      with header_groups.

    Returns a dictionary with two keys:
    * header_values contains a list of lists, one for each header group in
      header_groups.  Each list contains all the values for the corresponding
      header group as tuples.
    * groups contains a list of dicts, one for each row.  Each dict contains
      keys for each of the group_by fields, plus a 'group_count' key for the
      total count in the group, plus keys for each of the extra_select_fields.
      The keys for the extra_select_fields are determined by the "AS" alias of
      the field.
    """
    query = models.TestView.objects.get_query_set_with_joins(filter_data)
    # don't apply presentation yet, since we have extra selects to apply
    query = models.TestView.query_objects(filter_data, initial_query=query,
                                          apply_presentation=False)
    count_alias, count_sql = models.TestView.objects.get_count_sql(query)
    query = query.extra(select={count_alias: count_sql})
    if extra_select_fields:
        query = query.extra(select=extra_select_fields)
    query = models.TestView.apply_presentation(query, filter_data)

    group_processor = tko_rpc_utils.GroupDataProcessor(query, group_by,
                                                       header_groups or [],
                                                       fixed_headers or {})
    group_processor.process_group_dicts()
    return rpc_utils.prepare_for_serialization(group_processor.get_info_dict())


def get_num_groups(group_by, **filter_data):
    """
    Gets the count of unique groups with the given grouping fields.
    """
    query = models.TestView.objects.get_query_set_with_joins(filter_data)
    query = models.TestView.query_objects(filter_data, initial_query=query)
    return models.TestView.objects.get_num_groups(query, group_by)


def get_status_counts(group_by, header_groups=[], fixed_headers={},
                      **filter_data):
    """
    Like get_group_counts, but also computes counts of passed, complete (and
    valid), and incomplete tests, stored in keys "pass_count', 'complete_count',
    and 'incomplete_count', respectively.
    """
    return get_group_counts(group_by, header_groups=header_groups,
                            fixed_headers=fixed_headers,
                            extra_select_fields=tko_rpc_utils.STATUS_FIELDS,
                            **filter_data)


def get_latest_tests(group_by, header_groups=[], fixed_headers={},
                     extra_info=[], **filter_data):
    """
    Similar to get_status_counts, but return only the latest test result per
    group.  It still returns the same information (i.e. with pass count etc.)
    for compatibility.  It includes an additional field "test_idx" with each
    group.
    :param extra_info a list containing the field names that should be returned
                      with each cell. The fields are returned in the extra_info
                      field of the return dictionary.
    """
    # find latest test per group
    initial_query = models.TestView.objects.get_query_set_with_joins(
        filter_data)
    query = models.TestView.query_objects(filter_data,
                                          initial_query=initial_query,
                                          apply_presentation=False)
    query = query.exclude(status__in=tko_rpc_utils._INVALID_STATUSES)
    query = query.extra(
        select={'latest_test_idx': 'MAX(%s)' %
                models.TestView.objects.get_key_on_this_table('test_idx')})
    query = models.TestView.apply_presentation(query, filter_data)

    group_processor = tko_rpc_utils.GroupDataProcessor(query, group_by,
                                                       header_groups,
                                                       fixed_headers)
    group_processor.process_group_dicts()
    info = group_processor.get_info_dict()

    # fetch full info for these tests so we can access their statuses
    all_test_ids = [group['latest_test_idx'] for group in info['groups']]
    test_views = initial_query.in_bulk(all_test_ids)

    for group_dict in info['groups']:
        test_idx = group_dict.pop('latest_test_idx')
        group_dict['test_idx'] = test_idx
        test_view = test_views[test_idx]

        tko_rpc_utils.add_status_counts(group_dict, test_view.status)
        group_dict['extra_info'] = []
        for field in extra_info:
            group_dict['extra_info'].append(getattr(test_view, field))

    return rpc_utils.prepare_for_serialization(info)


def get_job_ids(**filter_data):
    """
    Returns AFE job IDs for all tests matching the filters.
    """
    query = models.TestView.query_objects(filter_data)
    job_ids = set()
    for test_view in query.values('job_tag').distinct():
        # extract job ID from tag
        first_tag_component = test_view['job_tag'].split('-')[0]
        try:
            job_id = int(first_tag_component)
            job_ids.add(job_id)
        except ValueError:
            # a nonstandard job tag, i.e. from contributed results
            pass
    return list(job_ids)


# test detail view

def _attributes_to_dict(attribute_list):
    return dict((attribute.attribute, attribute.value)
                for attribute in attribute_list)


def _iteration_attributes_to_dict(attribute_list):
    iter_keyfunc = operator.attrgetter('iteration')
    attribute_list.sort(key=iter_keyfunc)
    iterations = {}
    for key, group in itertools.groupby(attribute_list, iter_keyfunc):
        iterations[key] = _attributes_to_dict(group)
    return iterations


def _format_iteration_keyvals(test):
    iteration_attr = _iteration_attributes_to_dict(test.iteration_attributes)
    iteration_perf = _iteration_attributes_to_dict(test.iteration_results)

    all_iterations = iteration_attr.keys() + iteration_perf.keys()
    max_iterations = max(all_iterations + [0])

    # merge the iterations into a single list of attr & perf dicts
    return [{'attr': iteration_attr.get(index, {}),
             'perf': iteration_perf.get(index, {})}
            for index in xrange(1, max_iterations + 1)]


def _job_keyvals_to_dict(keyvals):
    return dict((keyval.key, keyval.value) for keyval in keyvals)


def get_detailed_test_views(**filter_data):
    test_views = models.TestView.list_objects(filter_data)

    tests_by_id = models.Test.objects.in_bulk([test_view['test_idx']
                                               for test_view in test_views])
    tests = tests_by_id.values()
    models.Test.objects.populate_relationships(tests, models.TestAttribute,
                                               'attributes')
    models.Test.objects.populate_relationships(tests, models.IterationAttribute,
                                               'iteration_attributes')
    models.Test.objects.populate_relationships(tests, models.IterationResult,
                                               'iteration_results')
    models.Test.objects.populate_relationships(tests, models.TestLabel,
                                               'labels')

    jobs_by_id = models.Job.objects.in_bulk([test_view['job_idx']
                                             for test_view in test_views])
    jobs = jobs_by_id.values()
    models.Job.objects.populate_relationships(jobs, models.JobKeyval,
                                              'keyvals')

    for test_view in test_views:
        test = tests_by_id[test_view['test_idx']]
        test_view['attributes'] = _attributes_to_dict(test.attributes)
        test_view['iterations'] = _format_iteration_keyvals(test)
        test_view['labels'] = [label.name for label in test.labels]

        job = jobs_by_id[test_view['job_idx']]
        test_view['job_keyvals'] = _job_keyvals_to_dict(job.keyvals)

    return rpc_utils.prepare_for_serialization(test_views)

# graphing view support


def get_hosts_and_tests():
    """
    Gets every host that has had a benchmark run on it. Additionally, also
    gets a dictionary mapping the host names to the benchmarks.
    """

    host_info = {}
    q = (dbmodels.Q(test_name__startswith='kernbench') |
         dbmodels.Q(test_name__startswith='dbench') |
         dbmodels.Q(test_name__startswith='tbench') |
         dbmodels.Q(test_name__startswith='unixbench') |
         dbmodels.Q(test_name__startswith='iozone'))
    test_query = models.TestView.objects.filter(q).values(
        'test_name', 'hostname', 'machine_idx').distinct()
    for result_dict in test_query:
        hostname = result_dict['hostname']
        test = result_dict['test_name']
        machine_idx = result_dict['machine_idx']
        host_info.setdefault(hostname, {})
        host_info[hostname].setdefault('tests', [])
        host_info[hostname]['tests'].append(test)
        host_info[hostname]['id'] = machine_idx
    return rpc_utils.prepare_for_serialization(host_info)


def create_metrics_plot(queries, plot, invert, drilldown_callback,
                        normalize=None):
    return graphing_utils.create_metrics_plot(
        queries, plot, invert, normalize, drilldown_callback=drilldown_callback)


def create_qual_histogram(query, filter_string, interval, drilldown_callback):
    return graphing_utils.create_qual_histogram(
        query, filter_string, interval, drilldown_callback=drilldown_callback)


# TODO(showard) - this extremely generic RPC is used only by one place in the
# client.  We should come up with a more opaque RPC for that place to call and
# get rid of this.
def execute_query_with_param(query, param):
    cursor = readonly_connection.connection().cursor()
    cursor.execute(query, param)
    return cursor.fetchall()


def get_preconfig(name, type):
    return preconfigs.manager.get_preconfig(name, type)


def get_embedding_id(url_token, graph_type, params):
    try:
        model = models.EmbeddedGraphingQuery.objects.get(url_token=url_token)
    except models.EmbeddedGraphingQuery.DoesNotExist:
        params_str = pickle.dumps(params)
        now = datetime.datetime.now()
        model = models.EmbeddedGraphingQuery(url_token=url_token,
                                             graph_type=graph_type,
                                             params=params_str,
                                             last_updated=now)
        model.cached_png = graphing_utils.create_embedded_plot(model,
                                                               now.ctime())
        model.save()

    return model.id


def get_embedded_query_url_token(id):
    model = models.EmbeddedGraphingQuery.objects.get(id=id)
    return model.url_token


# test label management

def add_test_label(name, description=None):
    return models.TestLabel.add_object(name=name, description=description).id


def modify_test_label(label_id, **data):
    models.TestLabel.smart_get(label_id).update_object(data)


def delete_test_label(label_id):
    models.TestLabel.smart_get(label_id).delete()


def get_test_labels(**filter_data):
    return rpc_utils.prepare_for_serialization(
        models.TestLabel.list_objects(filter_data))


def get_test_labels_for_tests(**test_filter_data):
    label_ids = models.TestView.objects.query_test_label_ids(test_filter_data)
    labels = models.TestLabel.list_objects({'id__in': label_ids})
    return rpc_utils.prepare_for_serialization(labels)


def test_label_add_tests(label_id, **test_filter_data):
    test_ids = models.TestView.objects.query_test_ids(test_filter_data)
    models.TestLabel.smart_get(label_id).tests.add(*test_ids)


def test_label_remove_tests(label_id, **test_filter_data):
    label = models.TestLabel.smart_get(label_id)

    # only include tests that actually have this label
    extra_where = test_filter_data.get('extra_where', '')
    if extra_where:
        extra_where = '(' + extra_where + ') AND '
    extra_where += 'tko_test_labels.id = %s' % label.id
    test_filter_data['extra_where'] = extra_where
    test_ids = models.TestView.objects.query_test_ids(test_filter_data)

    label.tests.remove(*test_ids)


# user-created test attributes

def set_test_attribute(attribute, value, **test_filter_data):
    """
    * attribute - string name of attribute
    * value - string, or None to delete an attribute
    * test_filter_data - filter data to apply to TestView to choose tests to act
      upon
    """
    assert test_filter_data  # disallow accidental actions on all hosts
    test_ids = models.TestView.objects.query_test_ids(test_filter_data)
    tests = models.Test.objects.in_bulk(test_ids)

    for test in tests.itervalues():
        test.set_or_delete_attribute(attribute, value)


# saved queries

def get_saved_queries(**filter_data):
    return rpc_utils.prepare_for_serialization(
        models.SavedQuery.list_objects(filter_data))


def add_saved_query(name, url_token):
    name = name.strip()
    owner = afe_models.User.current_user().login
    existing_list = list(models.SavedQuery.objects.filter(owner=owner,
                                                          name=name))
    if existing_list:
        query_object = existing_list[0]
        query_object.url_token = url_token
        query_object.save()
        return query_object.id

    return models.SavedQuery.add_object(owner=owner, name=name,
                                        url_token=url_token).id


def delete_saved_queries(id_list):
    user = afe_models.User.current_user().login
    query = models.SavedQuery.objects.filter(id__in=id_list, owner=user)
    if query.count() == 0:
        raise model_logic.ValidationError('No such queries found for this user')
    query.delete()


# other
def get_motd():
    return rpc_utils.get_motd()


def get_static_data():
    result = {}
    group_fields = []
    for field in models.TestView.group_fields:
        if field in models.TestView.extra_fields:
            name = models.TestView.extra_fields[field]
        else:
            name = models.TestView.get_field_dict()[field].verbose_name
        group_fields.append((name.capitalize(), field))
    model_fields = [(field.verbose_name.capitalize(), field.column)
                    for field in models.TestView._meta.fields]
    extra_fields = [(field_name.capitalize(), field_sql)
                    for field_sql, field_name
                    in models.TestView.extra_fields.iteritems()]

    benchmark_key = {
        'kernbench': 'elapsed',
        'dbench': 'throughput',
        'tbench': 'throughput',
        'unixbench': 'score',
        'iozone': '32768-4096-fwrite'
    }

    tko_perf_view = [
        ['Test Index', 'test_idx'],
        ['Job Index', 'job_idx'],
        ['Test Name', 'test_name'],
        ['Subdirectory', 'subdir'],
        ['Kernel Index', 'kernel_idx'],
        ['Status Index', 'status_idx'],
        ['Reason', 'reason'],
        ['Host Index', 'machine_idx'],
        ['Test Started Time', 'test_started_time'],
        ['Test Finished Time', 'test_finished_time'],
        ['Job Tag', 'job_tag'],
        ['Job Name', 'job_name'],
        ['Owner', 'job_owner'],
        ['Job Queued Time', 'job_queued_time'],
        ['Job Started Time', 'job_started_time'],
        ['Job Finished Time', 'job_finished_time'],
        ['Hostname', 'hostname'],
        ['Platform', 'platform'],
        ['Machine Owner', 'machine_owner'],
        ['Kernel Hash', 'kernel_hash'],
        ['Kernel Base', 'kernel_base'],
        ['Kernel', 'kernel'],
        ['Status', 'status'],
        ['Iteration Number', 'iteration'],
        ['Performance Keyval (Key)', 'iteration_key'],
        ['Performance Keyval (Value)', 'iteration_value'],
    ]

    result['group_fields'] = sorted(group_fields)
    result['all_fields'] = sorted(model_fields + extra_fields)
    result['test_labels'] = get_test_labels(sort_by=['name'])
    result['current_user'] = rpc_utils.prepare_for_serialization(
        afe_models.User.current_user().get_object_dict())
    result['benchmark_key'] = benchmark_key
    result['tko_perf_view'] = tko_perf_view
    result['tko_test_view'] = model_fields
    result['preconfigs'] = preconfigs.manager.all_preconfigs()
    result['motd'] = rpc_utils.get_motd()

    return result

# lower level access to tko models


def get_machines(**filter_data):
    return rpc_utils.prepare_for_serialization(
        models.Machine.list_objects(filter_data))


def get_kernels(**filter_data):
    return rpc_utils.prepare_for_serialization(
        models.Kernel.list_objects(filter_data))


def get_patches(**filter_data):
    return rpc_utils.prepare_for_serialization(
        models.Patch.list_objects(filter_data))


def get_statuses(**filter_data):
    return rpc_utils.prepare_for_serialization(
        models.Status.list_objects(filter_data))


def get_jobs(**filter_data):
    return rpc_utils.prepare_for_serialization(
        models.Job.list_objects(filter_data))


def get_job_keyvals(**filter_data):
    return rpc_utils.prepare_for_serialization(
        models.JobKeyval.list_objects(filter_data))


def get_tests(**filter_data):
    return rpc_utils.prepare_for_serialization(
        models.Test.list_objects(filter_data))


def get_test_attributes(**filter_data):
    return rpc_utils.prepare_for_serialization(
        models.TestAttribute.list_objects(filter_data))


def get_iteration_attributes(**filter_data):
    return rpc_utils.prepare_for_serialization(
        models.IterationAttribute.list_objects(filter_data))


def get_iteration_results(**filter_data):
    return rpc_utils.prepare_for_serialization(
        models.IterationResult.list_objects(filter_data))


def get_interface_version():
    return INTERFACE_VERSION
