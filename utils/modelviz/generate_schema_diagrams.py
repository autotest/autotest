#!/usr/bin/env python

"""
Generates schema diagrams for Django apps.  Just run the script with no
arguments.  If you don't have them installed, you'll need "dot" from the
Graphviz package and Django.
"""

import common
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PROJECTS = (
        ('frontend', 'tko'),
        ('frontend', 'afe'),
    )


def main():
    for project, app in PROJECTS:
        settings = 'autotest_lib.%s.settings' % project
        os.environ['DJANGO_SETTINGS_MODULE'] = settings

        # import after setting DJANGO_SETTINGS_MODULE
        from autotest_lib.contrib import modelviz

        # hack to force reload of settings and app list
        import django.conf
        from django.db.models import loading
        reload(django.conf)
        reload(loading)

        print 'Analyzing', project
        dot_contents = modelviz.generate_dot([app])

        dot_path = project + '.dot'
        dotfile = open(dot_path, 'w')
        dotfile.write(dot_contents)
        dotfile.close()
        print 'Wrote', dot_path

        png_path = project + '.png'
        os.system('dot -Tpng -o %s %s' % (png_path, dot_path))
        print 'Generated', png_path
        print

        del os.environ['DJANGO_SETTINGS_MODULE']


if __name__ == '__main__':
    main()
