from autotest_lib.frontend.afe import rpc_utils
from autotest_lib.client.bin import kernel_versions

MAX_GROUP_RESULTS = 50000

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


class GroupDataProcessor(object):
    def __init__(self, group_by, header_groups, extra_fields):
        self._group_by = group_by
        self._num_group_fields = len(group_by)
        self._header_value_sets = [set() for i
                                   in xrange(len(header_groups))]
        self._header_groups = header_groups
        self._sorted_header_values = None
        self._extra_fields = extra_fields


    @staticmethod
    def _get_field(group_dict, field):
        """
        Wraps kernel versions with a KernelString so they sort properly.
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


    def get_group_dict(self, count_row):
        group_values = count_row[:self._num_group_fields]
        group_dict = dict(zip(self._group_by, group_values))
        group_dict['group_count'] = count_row[self._num_group_fields]

        extra_values = [int(value)
                        for value in count_row[(self._num_group_fields + 1):]]
        group_dict.update(zip(self._extra_fields, extra_values))

        # compute and aggregate header groups
        for i, group in enumerate(self._header_groups):
            header = tuple(self._get_field(group_dict, field)
                           for field in group)
            self._header_value_sets[i].add(header)
            group_dict.setdefault('header_values', []).append(header)

        # frontend's SelectionManager needs a unique ID
        group_dict['id'] = str(group_values)
        return group_dict


    def get_sorted_header_values(self):
        sorted_header_values = [sorted(value_set)
                                for value_set in self._header_value_sets]
        # construct dicts mapping headers to their indices, for use in
        # replace_headers_with_indices()
        self._header_index_maps = []
        for value_list in sorted_header_values:
            index_map = dict((value, i) for i, value in enumerate(value_list))
            self._header_index_maps.append(index_map)

        return sorted_header_values


    def replace_headers_with_indices(self, group_dict):
        group_dict['header_indices'] = [index_map[header_value]
                                        for index_map, header_value
                                        in zip(self._header_index_maps,
                                               group_dict['header_values'])]
        for field in self._group_by + ['header_values']:
            del group_dict[field]
