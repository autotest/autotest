# -*- coding: utf-8 -*-

import sys
import os

try:
    import autotest.client.setup_modules as setup_modules
    dirname = os.path.dirname(setup_modules.__file__)
    autotest_dir = os.path.join(dirname, "..", "..")
except ImportError:
    dirname = os.path.dirname(__file__)
    autotest_dir = os.path.abspath(os.path.join(dirname, "..", ".."))
    client_dir = os.path.join(autotest_dir, "client")
    sys.path.insert(0, client_dir)
    import setup_modules
    sys.path.pop(0)

setup_modules.setup(base_path=autotest_dir, root_module_name="autotest")

from autotest.client.shared.version import get_version
os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                      "autotest.documentation.source.settings")


extensions = ['sphinx.ext.autodoc',
              'sphinx.ext.doctest',
              'sphinx.ext.intersphinx',
              'sphinx.ext.todo',
              'sphinx.ext.coverage',
              'sphinx.ext.ifconfig',
              'sphinx.ext.viewcode']


master_doc = 'index'
project = u'autotest'
copyright = u'2013, Autotest Team'

v_parts = get_version().split('.')
version = "%s.%s" % (v_parts[0], v_parts[1])
release = '%s.%s.%s' % (v_parts[0], v_parts[1], v_parts[2])

# on_rtd is whether we are on readthedocs.org, this line of code grabbed from docs.readthedocs.org
on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

if not on_rtd:  # only import and set the theme if we're building docs locally
    try:
        import sphinx_rtd_theme
        html_theme = 'sphinx_rtd_theme'
        html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
    except ImportError:
        html_theme = 'default'

pygments_style = 'sphinx'

latex_documents = [
    ('index', 'autotest.tex', u'autotest Documentation',
     u'Autotest Team', 'manual'),
]

man_pages = [
    ('index', 'autotest', u'autotest Documentation',
     [u'Autotest Team'], 1)
]


texinfo_documents = [
    ('index', 'autotest', u'autotest Documentation',
     u'Autotest Team', 'autotest', 'One line description of project.',
     'Miscellaneous'),
]

epub_title = u'autotest'
epub_author = u'Autotest Team'
epub_publisher = u'Autotest Team'
epub_copyright = u'2013, Autotest Team'

# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {
    'python': ('http://docs.python.org/', None),
    'django': ('http://docs.djangoproject.com/en/dev/',
               'http://docs.djangoproject.com/en/dev/_objects/')
}


class Mock(object):
    #__all__ = []
    version_info = (1, 2, 3, 'final', 0)

    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return Mock()

    @classmethod
    def __getattr__(cls, name):
        if name in ('__file__', '__path__'):
            return '/dev/null'
        elif name[0] == name[0].upper():
            mockType = type(name, (), {})
            mockType.__module__ = __name__
            return mockType
        else:
            return Mock()

MOCK_MODULES = ['MySQLdb', 'psutil']
for mod_name in MOCK_MODULES:
    sys.modules[mod_name] = Mock()
