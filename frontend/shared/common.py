import os
import sys
try:
    import autotest.client.setup_modules as setup_modules
    dirname = os.path.dirname(setup_modules.__file__)
    autotest_dir = os.path.join(dirname, "..")
except ImportError:
    dirname = os.path.dirname(sys.modules[__name__].__file__)
    autotest_dir = os.path.abspath(os.path.join(dirname, '..', '..'))
    client_dir = os.path.join(autotest_dir, "client")
    sys.path.insert(0, client_dir)
    import setup_modules
    sys.path.pop(0)

setup_modules.setup(base_path=autotest_dir, root_module_name="autotest")
