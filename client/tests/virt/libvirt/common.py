import os, sys

def load_setup_modules(client_dir):
    try:
        sys.path.insert(0, client_dir)
        import setup_modules
    finally:
        sys.path.pop(0)
    return setup_modules

try:
    import autotest.client.setup_modules as setup_modules
    client_dir = os.path.dirname(setup_modules.__file__)
    sm = setup_modules
except ImportError:
    dirname = os.path.dirname(sys.modules[__name__].__file__)
    try:
        client_dir = os.path.abspath(os.path.join(dirname, "..", "..", ".."))
        sm = load_setup_modules(client_dir)
    except:
        try:
            client_dir = os.path.join(os.environ['AUTOTEST_PATH'], 'client')
        except KeyError:
            print("Environment variable $AUTOTEST_PATH not set. "
                  "please set it to a path containing an autotest checkout")
            sys.exit(1)
        sm = load_setup_modules(client_dir)
    virt_test_dir = os.path.abspath(os.path.join(dirname, ".."))
    sys.path.insert(0, virt_test_dir)

sm.setup(base_path=client_dir, root_module_name="autotest.client")
