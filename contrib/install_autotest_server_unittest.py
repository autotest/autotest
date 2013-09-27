#  Copyright(c) 2013 Intel Corporation.
#
#  This program is free software; you can redistribute it and/or modify it
#  under the terms and conditions of the GNU General Public License,
#  version 2, as published by the Free Software Foundation.
#
#  This program is distributed in the hope it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
#  FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
#  more details.
#
#  You should have received a copy of the GNU General Public License along with
#  this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin St - Fifth Floor, Boston, MA 02110-1301 USA.
#
#  The full GNU General Public License is included in this distribution in
#  the file called "COPYING".

from cStringIO import StringIO
import unittest
import sys

try:
    import autotest.common as common
except ImportError:
    import common

from autotest.client.shared.mock import patch, MagicMock


pwd_mock = patch.dict("sys.modules", pwd=MagicMock(), locale=MagicMock())
pwd_mock.start()
import install_autotest_server
pwd_mock.stop()


class TestIt(unittest.TestCase):

    @staticmethod
    def test_parse_args():
        a = sys.argv
        stdout = StringIO()
        try:
            sys.argv = ["install_autotest_server.py", "-h"]
            sys.stdout = stdout
            try:
                install_autotest_server.parse_args()
            except SystemExit:
                pass
        finally:
            sys.argv = a
        assert stdout.getvalue().startswith("Usage: install")

    @staticmethod
    def test_freespace():
        assert install_autotest_server.freespace(".") > 0

    @staticmethod
    def test_checK_disk_space():
        install_autotest_server.check_disk_space()
