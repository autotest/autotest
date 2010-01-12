import csv
import django.http
import common
from autotest_lib.frontend.afe import rpc_utils

class CsvEncoder(object):
    def __init__(self, request, response):
        self._request = request
        self._response = response
        self._output_rows = []


    def _append_output_row(self, row):
        self._output_rows.append(row)


    def _build_response(self):
        response = django.http.HttpResponse(mimetype='text/csv')
        response['Content-Disposition'] = (
            'attachment; filename=tko_query.csv')
        writer = csv.writer(response)
        writer.writerows(self._output_rows)
        return response


    def encode(self):
        raise NotImplemented


class UnhandledMethodEncoder(CsvEncoder):
    def encode(self):
        return rpc_utils.raw_http_response(
            'Unhandled method %s (this indicates a bug)\r\n' %
            self._request['method'])


class SpreadsheetCsvEncoder(CsvEncoder):
    def _total_index(self, group, num_columns):
        row_index, column_index = group['header_indices']
        return row_index * num_columns + column_index


    def _group_string(self, group):
        result = '%s / %s' % (group['pass_count'], group['complete_count'])
        if group['incomplete_count'] > 0:
            result +=  ' (%s incomplete)' % group['incomplete_count']
        if 'extra_info' in group:
            result = '\n'.join([result] + group['extra_info'])
        return result


    def _build_value_table(self):
        value_table = [''] * self._num_rows * self._num_columns
        for group in self._response['groups']:
            total_index = self._total_index(group, self._num_columns)
            value_table[total_index] = self._group_string(group)
        return value_table


    def _header_string(self, header_value):
        return '/'.join(header_value)


    def _process_value_table(self, value_table, row_headers):
        total_index = 0
        for row_index in xrange(self._num_rows):
            row_header = self._header_string(row_headers[row_index])
            row_end_index = total_index + self._num_columns
            row_values = value_table[total_index:row_end_index]
            self._append_output_row([row_header] + row_values)
            total_index += self._num_columns


    def encode(self):
        header_values = self._response['header_values']
        assert len(header_values) == 2
        row_headers, column_headers = header_values
        self._num_rows, self._num_columns = (len(row_headers),
                                             len(column_headers))

        value_table = self._build_value_table()

        first_line = [''] + [self._header_string(header_value)
                            for header_value in column_headers]
        self._append_output_row(first_line)
        self._process_value_table(value_table, row_headers)

        return self._build_response()


class TableCsvEncoder(CsvEncoder):
    def __init__(self, request, response):
        super(TableCsvEncoder, self).__init__(request, response)
        self._column_specs = request['columns']


    def _format_row(self, row_object):
        """Extract data from a row object into a list of strings"""
        return [row_object.get(field) for field, name in self._column_specs]


    def _encode_table(self, row_objects):
        self._append_output_row([column_spec[1] # header row
                                 for column_spec in self._column_specs])
        for row_object in row_objects:
            self._append_output_row(self._format_row(row_object))
        return self._build_response()


    def encode(self):
        return self._encode_table(self._response)


class GroupedTableCsvEncoder(TableCsvEncoder):
    def encode(self):
        return self._encode_table(self._response['groups'])


class StatusCountTableCsvEncoder(GroupedTableCsvEncoder):
    _PASS_RATE_FIELD = '_test_pass_rate'

    def __init__(self, request, response):
        super(StatusCountTableCsvEncoder, self).__init__(request, response)
        # inject a more sensible field name for test pass rate
        for column_spec in self._column_specs:
            field, name = column_spec
            if name == 'Test pass rate':
                column_spec[0] = self._PASS_RATE_FIELD
                break


    def _format_pass_rate(self, row_object):
        result = '%s / %s' % (row_object['pass_count'],
                              row_object['complete_count'])
        incomplete_count = row_object['incomplete_count']
        if incomplete_count:
            result += ' (%s incomplete)' % incomplete_count
        return result


    def _format_row(self, row_object):
        row_object[self._PASS_RATE_FIELD] = self._format_pass_rate(row_object)
        return super(StatusCountTableCsvEncoder, self)._format_row(row_object)


_ENCODER_MAP = {
    'get_latest_tests' : SpreadsheetCsvEncoder,
    'get_test_views' : TableCsvEncoder,
    'get_group_counts' : GroupedTableCsvEncoder,
}


def _get_encoder_class(request):
    method = request['method']
    if method in _ENCODER_MAP:
        return _ENCODER_MAP[method]
    if method == 'get_status_counts':
        if 'columns' in request:
            return StatusCountTableCsvEncoder
        return SpreadsheetCsvEncoder
    return UnhandledMethodEncoder


def encoder(request, response):
    EncoderClass = _get_encoder_class(request)
    return EncoderClass(request, response)
