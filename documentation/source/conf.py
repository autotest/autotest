# -*- coding: utf-8 -*-

import sys
import os


class DocBuildError(Exception):
    pass

root_path = os.path.abspath(os.path.join("..", ".."))
import commands
_sphinx_apidoc = commands.getoutput('which sphinx-apidoc').strip()
_output_dir = os.path.join(root_path, 'documentation', 'source', 'api')
_api_dir = os.path.join(root_path, 'autotest')
if os.path.exists(_api_dir) and not os.path.islink(_api_dir):
    raise DocBuildError('Something is wrong with your build directory: %s' %
                        os.listdir(root_path))
if not os.path.islink(_api_dir):
    os.symlink(root_path, _api_dir)

_excluded_paths = []
_excluded_paths.append('%s/documentation' % _api_dir)
_excluded_paths.append('%s/database_legacy' % _api_dir)
_excluded_paths.append('%s/frontend' % _api_dir)
_excluded_paths.append('%s/contrib' % _api_dir)
_excluded_paths.append('%s/installation_support' % _api_dir)
_excluded_paths.append('%s/scheduler' % _api_dir)
_excluded_paths.append('%s/mirror' % _api_dir)
_excluded_paths.append('%s/tko' % _api_dir)
_excluded_paths.append('%s/utils' % _api_dir)

_excluded_paths = " ".join(_excluded_paths)

_sphinx_apidoc = "%s -o %s %s %s" % (_sphinx_apidoc, _output_dir, _api_dir, _excluded_paths)
print(_sphinx_apidoc)
_status, _output = commands.getstatusoutput(_sphinx_apidoc)
if _status:
    raise DocBuildError("API rst auto generation failed: %s" % _output)

sys.path.insert(0, root_path)

import autotest.client.shared.version

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

v_parts = autotest.client.shared.version.get_version().split('.')
version = "%s.%s" % (v_parts[0], v_parts[1])
release = '%s.%s.%s' % (v_parts[0], v_parts[1], v_parts[2])

pygments_style = 'sphinx'

on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

if not on_rtd:  # only import and set the theme if we're building docs locally
    try:
        import sphinx_rtd_theme
        html_theme = 'sphinx_rtd_theme'
        html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
    except ImportError:
        html_theme = 'default'

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
