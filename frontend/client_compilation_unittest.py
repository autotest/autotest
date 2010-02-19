#!/usr/bin/python

import os, shutil, tempfile, unittest
import common

_AUTOTEST_DIR = common.autotest_dir


class ClientCompilationTest(unittest.TestCase):


    def _compile_module(self, module_name):
        compile_script = os.path.join(_AUTOTEST_DIR, 'utils',
                                       'compile_gwt_clients.py')
        cmd = '%s -d -c %s -e "-validateOnly"' % (compile_script, module_name)
        result = os.system(cmd)
        self.assertEquals(result, 0)


    def test_afe_compilation(self):
        self._compile_module('autotest.AfeClient')


    def test_tko_compilation(self):
        self._compile_module('autotest.TkoClient')


    def test_embedded_tko_compilation(self):
        self._compile_module('autotest.EmbeddedTkoClient')


if __name__ == '__main__':
    unittest.main()
