#!/usr/bin/python

import unittest, os

COMPILE_SCRIPT_DIR = os.path.join(os.path.dirname(__file__), 'client')

class ClientCompilationTest(unittest.TestCase):
    def _compile_module(self, module_name):
        compile_script = module_name + '-compile'
        full_path = os.path.join(COMPILE_SCRIPT_DIR, compile_script)
        result = os.system(full_path + ' -validateOnly')
        self.assertEquals(result, 0)


    def test_afe_compilation(self):
        self._compile_module('AfeClient')


    def test_tko_compilation(self):
        self._compile_module('TkoClient')


if __name__ == '__main__':
    unittest.main()
