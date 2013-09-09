#!/usr/bin/python

import os
import shutil
import tempfile
import unittest
import logging
try:
    import autotest.common as common
except ImportError:
    import common
from autotest.client import utils

_AUTOTEST_DIR = common.autotest_dir


class ClientCompilationTest(unittest.TestCase):

    def _compile_module(self, module_name):
        compile_script = os.path.join(_AUTOTEST_DIR, 'utils',
                                      'compile_gwt_clients.py')
        cmd = '%s -d -c %s -e "-validateOnly"' % (compile_script, module_name)
        result = utils.run(cmd, verbose=False, ignore_status=True)
        result = result.exit_status
        self.assertEquals(result, 0)

    def test_afe_compilation(self):
        self._compile_module('autotest.AfeClient')

    def test_tko_compilation(self):
        self._compile_module('autotest.TkoClient')

    def test_embedded_tko_compilation(self):
        self._compile_module('autotest.EmbeddedTkoClient')


if __name__ == '__main__':
    unittest.main()
