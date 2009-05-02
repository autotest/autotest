#!/usr/bin/python2.4

import unittest
import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend import setup_test_environment
from autotest_lib.new_tko.tko import csv_encoder

class CsvEncodingTest(unittest.TestCase):
    def _make_request(self, method):
        return dict(method=method)


    def _make_group(self, header_indices, pass_count, complete_count,
                    incomplete_count=0):
        return dict(header_indices=header_indices, pass_count=pass_count,
                    complete_count=complete_count,
                    incomplete_count=incomplete_count)


    def _encode_and_check_result(self, request, result, expected_csv):
        encoder = csv_encoder.encoder(request, result)
        response = encoder.encode()
        csv_result = response.content
        self.assertEquals(csv_result, expected_csv)


    def test_spreadsheet_encoder(self):
        request = self._make_request('get_status_counts')
        response = {'header_values' :
                        [[('row1',), ('row2',), ('comma,header',)],
                         [('col1', 'sub1'), ('col1', 'sub2'),
                          ('col2', 'sub1')]],
                    'groups' : [self._make_group((0, 0), 1, 2),
                                self._make_group((1, 2), 3, 4, 5)]}

        self._encode_and_check_result(request, response,
                                      ',col1/sub1,col1/sub2,col2/sub1\r\n'
                                      'row1,1 / 2,,\r\n'
                                      'row2,,,3 / 4 (5 incomplete)\r\n'
                                      '"comma,header",,,\r\n')


    def test_unhandled_method(self):
        request = self._make_request('foo')
        self._encode_and_check_result(request, None,
                                      'Unhandled method foo (this indicates a '
                                      'bug)\n')


if __name__ == '__main__':
    unittest.main()
