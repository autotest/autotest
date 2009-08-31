from autotest_lib.frontend.afe import rpc_utils
from autotest_lib.client.common_lib import kernel_versions
from autotest_lib.new_tko.tko import models

class TooManyRowsError(Exception):
    """
    Raised when a database query returns too many rows.
    """


class KernelString(str):
    """
    Custom string class that uses correct kernel version comparisons.
    """
    def _map(self):
        return kernel_versions.version_encode(self)


    def __hash__(self):
        return hash(self._map())


    def __eq__(self, other):
        return self._map() == other._map()


    def __ne__(self, other):
        return self._map() != other._map()


    def __lt__(self, other):
        return self._map() < other._map()


    def __lte__(self, other):
        return self._map() <= other._map()


    def __gt__(self, other):
        return self._map() > other._map()


    def __gte__(self, other):
        return self._map() >= other._map()


# SQL expression to compute passed test count for test groups
_PASS_COUNT_NAME = 'pass_count'
_COMPLETE_COUNT_NAME = 'complete_count'
_INCOMPLETE_COUNT_NAME = 'incomplete_count'
# Using COUNT instead of SUM here ensures the resulting row has the right type
# (i.e. numeric, not string).  I don't know why.
_PASS_COUNT_SQL = 'COUNT(IF(status="GOOD", 1, NULL))'
_COMPLETE_COUNT_SQL = ('COUNT(IF(status NOT IN ("TEST_NA", "RUNNING", '
                                               '"NOSTATUS"), 1, NULL))')
_INCOMPLETE_COUNT_SQL = 'COUNT(IF(status="RUNNING", 1, NULL))'
STATUS_FIELDS = {_PASS_COUNT_NAME : _PASS_COUNT_SQL,
                 _COMPLETE_COUNT_NAME : _COMPLETE_COUNT_SQL,
                 _INCOMPLETE_COUNT_NAME : _INCOMPLETE_COUNT_SQL}
_INVALID_STATUSES = ('TEST_NA', 'NOSTATUS')


def add_status_counts(group_dict, status):
    pass_count = complete_count = incomplete_count = 0
    if status == 'GOOD':
        pass_count = complete_count = 1
    elif status == 'RUNNING':
        incomplete_count = 1
    else:
        complete_count = 1
    group_dict[_PASS_COUNT_NAME] = pass_count
    group_dict[_COMPLETE_COUNT_NAME] = complete_count
    group_dict[_INCOMPLETE_COUNT_NAME] = incomplete_count
    group_dict[models.TestView.objects._GROUP_COUNT_NAME] = 1


def _construct_machine_label_header_sql(machine_labels):
    """
    Example result for machine_labels=['Index', 'Diskful']:
    CONCAT_WS(",",
              IF(FIND_IN_SET("Diskful", test_attributes_host_labels.value),
                 "Diskful", NULL),
              IF(FIND_IN_SET("Index", test_attributes_host_labels.value),
                 "Index", NULL))

    This would result in field values "Diskful,Index", "Diskful", "Index", NULL.
    """
    machine_labels = sorted(machine_labels)
    if_clauses = []
    for label in machine_labels:
        if_clauses.append(
            'IF(FIND_IN_SET("%s", test_attributes_host_labels.value), '
               '"%s", NULL)' % (label, label))
    return 'CONCAT_WS(",", %s)' % ', '.join(if_clauses)


def add_machine_label_headers(machine_label_headers, extra_selects):
    for field_name, machine_labels in machine_label_headers.iteritems():
        extra_selects[field_name] = (
            _construct_machine_label_header_sql(machine_labels))


class GroupDataProcessor(object):
    _MAX_GROUP_RESULTS = 80000

    def __init__(self, query, group_by, header_groups, fixed_headers,
                 extra_select_fields):
        self._query = query
        self._group_by = self.uniqify(group_by)
        self._header_groups = header_groups
        self._fixed_headers = dict((field, set(values))
                                   for field, values
                                   in fixed_headers.iteritems())
        self._extra_select_fields = extra_select_fields

        self._num_group_fields = len(group_by)
        self._header_value_sets = [set() for i
                                   in xrange(len(header_groups))]
        self._group_dicts = []


    @staticmethod
    def uniqify(values):
        return list(set(values))


    def _restrict_header_values(self):
        for header_field, values in self._fixed_headers.iteritems():
            self._query = self._query.filter(**{header_field + '__in' : values})


    def _fetch_data(self):
        self._restrict_header_values()
        self._group_dicts = models.TestView.objects.execute_group_query(
            self._query, self._group_by, self._extra_select_fields)


    @staticmethod
    def _get_field(group_dict, field):
        """
        Use special objects for certain fields to achieve custom sorting.
        -Wrap kernel versions with a KernelString
        -Replace null dates with special values
        """
        value = group_dict[field]
        if field == 'kernel':
            return KernelString(value)
        if value is None: # handle null dates as later than everything else
            if field.startswith('DATE('):
                return rpc_utils.NULL_DATE
            if field.endswith('_time'):
                return rpc_utils.NULL_DATETIME
        return value


    def _process_group_dict(self, group_dict):
        # compute and aggregate header groups
        for i, group in enumerate(self._header_groups):
            header = tuple(self._get_field(group_dict, field)
                           for field in group)
            self._header_value_sets[i].add(header)
            group_dict.setdefault('header_values', []).append(header)

        # frontend's SelectionManager needs a unique ID
        group_values = [group_dict[field] for field in self._group_by]
        group_dict['id'] = str(group_values)
        return group_dict


    def _find_header_value_set(self, field):
        for i, group in enumerate(self._header_groups):
            if [field] == group:
                return self._header_value_sets[i]
        raise RuntimeError('Field %s not found in header groups %s' %
                           (field, self._header_groups))


    def _add_fixed_headers(self):
        for field, extra_values in self._fixed_headers.iteritems():
            header_value_set = self._find_header_value_set(field)
            for value in extra_values:
                header_value_set.add((value,))


    def _get_sorted_header_values(self):
        self._add_fixed_headers()
        sorted_header_values = [sorted(value_set)
                                for value_set in self._header_value_sets]
        # construct dicts mapping headers to their indices, for use in
        # replace_headers_with_indices()
        self._header_index_maps = []
        for value_list in sorted_header_values:
            index_map = dict((value, i) for i, value in enumerate(value_list))
            self._header_index_maps.append(index_map)

        return sorted_header_values


    def _replace_headers_with_indices(self, group_dict):
        group_dict['header_indices'] = [index_map[header_value]
                                        for index_map, header_value
                                        in zip(self._header_index_maps,
                                               group_dict['header_values'])]
        for field in self._group_by + ['header_values']:
            del group_dict[field]


    def process_group_dicts(self):
        self._fetch_data()
        if len(self._group_dicts) > self._MAX_GROUP_RESULTS:
            raise TooManyRowsError(
                'Query yielded %d rows, exceeding maximum %d' % (
                len(self._group_dicts), self._MAX_GROUP_RESULTS))

        for group_dict in self._group_dicts:
            self._process_group_dict(group_dict)
        self._header_values = self._get_sorted_header_values()
        if self._header_groups:
            for group_dict in self._group_dicts:
                self._replace_headers_with_indices(group_dict)


    def get_info_dict(self):
        return {'groups' : self._group_dicts,
                'header_values' : self._header_values}


def extract_presentation_params(test_filter_data):
    """
    Extract presentation-related parameters from test_filter_data -- pagination
    limits and sorting.
    """
    extracted_data = {}
    for key in ('query_start', 'query_limit', 'sort_by'):
        extracted_data[key] = test_filter_data.pop(key, None)
    return extracted_data


def get_iteration_view_query(result_keys, test_filter_data):
    filter_data = dict(test_filter_data) # copy, don't mutate
    extract_presentation_params(filter_data)
    test_ids = models.TestView.objects.query_test_ids(filter_data)
    test_views = models.TestView.objects.filter(pk__in=test_ids)
    iteration_views = models.TestView.objects.join_iterations(test_views,
                                                              result_keys)
    return iteration_views
