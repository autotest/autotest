import os
import distutils.ccompiler
import distutils.sysconfig

PYTHON_HEADERS = distutils.sysconfig.get_python_inc()
PYTHON_VERSION = distutils.sysconfig.get_python_version()
PYTHON_LIB = "python%s" % PYTHON_VERSION

ABSPATH = os.path.abspath(__file__)
OUTPUT_DIR = os.path.dirname(ABSPATH)

SOURCES = [os.path.join(OUTPUT_DIR, f) for f in ['passfd.c']]
SHARED_OBJECT = os.path.join(OUTPUT_DIR, '_passfd.so')

def passfd_setup(output_dir=OUTPUT_DIR):
    '''
    Compiles the passfd python extension

    @param output_dir: where the _passfd.so module will be saved
    @return: None
    '''
    if output_dir is not None:
        output_file = os.path.join(output_dir, SHARED_OBJECT)
    else:
        output_file = SHARED_OBJECT

    c = distutils.ccompiler.new_compiler()
    objects = c.compile(SOURCES, include_dirs=[PYTHON_HEADERS], extra_postargs=['-fPIC'])
    c.link_shared_object(objects, SHARED_OBJECT, libraries=[PYTHON_LIB])


def import_passfd():
    '''
    Imports and lazily sets up the passfd module

    @return: passfd module
    '''
    try:
        import passfd
    except ImportError:
        passfd_setup()
    import passfd
    return passfd


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        passfd_setup(sys.argv[1])
    else:
        passfd_setup()
