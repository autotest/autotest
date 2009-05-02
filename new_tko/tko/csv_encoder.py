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
            'Unhandled method %s (this indicates a bug)\n' %
            self._request['method'])


class SpreadsheetCsvEncoder(CsvEncoder):
    def _total_index(self, group, num_columns):
        row_index, column_index = group['header_indices']
        return row_index * num_columns + column_index


    def _group_string(self, group):
        result = '%s / %s' % (group['pass_count'], group['complete_count'])
        if group['incomplete_count'] > 0:
            result +=  ' (%s incomplete)' % group['incomplete_count']
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


_ENCODER_MAP = {
    'get_status_counts' : SpreadsheetCsvEncoder,
    'get_latest_tests' : SpreadsheetCsvEncoder,
}


def encoder(request, response):
    method = request['method']
    EncoderClass = _ENCODER_MAP.get(method, UnhandledMethodEncoder)
    return EncoderClass(request, response)
