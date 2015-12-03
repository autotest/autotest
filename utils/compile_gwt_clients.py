#!/usr/bin/python
try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
import logging
import optparse
import os
import shutil
import sys

from autotest.client.shared import error, utils
from autotest.client.shared import logging_config, logging_manager

"""
Compile All Autotest GWT Clients Living in autotest/frontend/client/src
"""

_AUTOTEST_DIR = common.autotest_dir
_DEFAULT_GWT_DIR = '/usr/share/gwt'
if not os.path.isdir(_DEFAULT_GWT_DIR):
    _DEFAULT_GWT_DIR = '/usr/local/lib/gwt'
_DEFAULT_APP_DIR = os.path.join(_AUTOTEST_DIR, 'frontend/client')
_DEFAULT_INSTALL_DIR = os.path.join(_DEFAULT_APP_DIR, 'www')
_TMP_COMPILE_DIR = _DEFAULT_INSTALL_DIR + '.new'

_COMPILE_LINE = ('java  -Xmx512M '
                 '-cp "%(app_dir)s/src:%(app_dir)s/bin:%(gwt_dir)s/gwt-user.jar'
                 ':%(gwt_dir)s/gwt-dev.jar" -Djava.awt.headless=true '
                 'com.google.gwt.dev.Compiler -war "%(compile_dir)s" '
                 '%(extra_args)s %(project_client)s')


class CompileClientsLoggingConfig(logging_config.LoggingConfig):

    def configure_logging(self, results_dir=None, verbose=False):
        super(CompileClientsLoggingConfig, self).configure_logging(
            use_console=True,
            verbose=verbose)


def enumerate_projects():
    """List projects in _DEFAULT_APP_DIR."""
    src_path = os.path.join(_DEFAULT_APP_DIR, 'src')
    projects = {}
    for project in os.listdir(src_path):
        projects[project] = []
        project_path = os.path.join(src_path, project)
        for file in os.listdir(project_path):
            if file.endswith('.gwt.xml'):
                projects[project].append(file[:-8])
    return projects


def find_gwt_dir():
    """See if GWT is installed in site-packages or in the system,
       site-packages is favored over a system install.
    """
    site_gwt = os.path.join(_AUTOTEST_DIR, 'site-packages', 'gwt')

    if os.path.isdir(site_gwt):
        return site_gwt

    if not os.path.isdir(_DEFAULT_GWT_DIR):
        logging.error('Unable to find GWT. '
                      'You can use utils/build_externals.py to install it.')
        sys.exit(1)

    return _DEFAULT_GWT_DIR


def install_completed_client(compiled_dir, project_client):
    """Remove old client directory if it exists,  move installed client to the
       old directory and move newly compield client to the installed client
       dir.
       :param compiled_dir: Where the new client was compiled
       :param project_client: project.client pair e.g. autotest.AfeClient
       :return: True if installation was successful or False if it failed
    """
    tmp_client_dir = os.path.join(_TMP_COMPILE_DIR, project_client)
    install_dir = os.path.join(_DEFAULT_INSTALL_DIR, project_client)
    old_install_dir = os.path.join(_DEFAULT_INSTALL_DIR,
                                   project_client + '.old')
    if not os.path.exists(_DEFAULT_INSTALL_DIR):
        os.mkdir(_DEFAULT_INSTALL_DIR)

    if os.path.isdir(tmp_client_dir):
        if os.path.isdir(old_install_dir):
            shutil.rmtree(old_install_dir)
        if os.path.isdir(install_dir):
            os.rename(install_dir, old_install_dir)
        try:
            os.rename(tmp_client_dir, install_dir)
            return True
        except Exception, err:
            # If we can't rename the client raise an exception
            # and put the old client back
            shutil.rmtree(install_dir)
            shutil.copytree(old_install_dir, install_dir)
            logging.error('Copying old client: %s', err)
    else:
        logging.error('Compiled directory is gone, something went wrong')

    return False


def compile_and_install_client(project_client, extra_args='',
                               install_client=True):
    """Compile the client into a temporary directory, if successful
       call install_completed_client to install the new client.
       :param project_client: project.client pair e.g. autotest.AfeClient
       :param install_client: Boolean, if True install the clients
       :return: True if install and compile was successful False if it failed
    """
    java_args = {}
    java_args['compile_dir'] = _TMP_COMPILE_DIR
    java_args['app_dir'] = _DEFAULT_APP_DIR
    java_args['gwt_dir'] = find_gwt_dir()
    java_args['extra_args'] = extra_args
    java_args['project_client'] = project_client
    cmd = _COMPILE_LINE % java_args

    logging.info('Compiling client %s', project_client)
    try:
        utils.run(cmd, verbose=True)
        if install_client:
            return install_completed_client(java_args['compile_dir'],
                                            project_client)
        return True
    except error.CmdError:
        logging.info('Error compiling %s, leaving old client', project_client)

    return False


def compile_all_projects(projects, extra_args=''):
    """Compile all projects available as defined by enumerate_projects.
       :return: list of failed client installations
    """
    failed_clients = []
    for project, clients in enumerate_projects().iteritems():
        for client in clients:
            project_client = '%s.%s' % (project, client)
            if not compile_and_install_client(project_client, extra_args):
                failed_clients.append(project_client)

    return failed_clients


def print_projects():
    logging.info('Projects that can be compiled:')
    for project, clients in enumerate_projects().iteritems():
        for client in clients:
            logging.info('%s.%s', project, client)


def main():
    logging_manager.configure_logging(CompileClientsLoggingConfig(),
                                      verbose=True)
    parser = optparse.OptionParser()
    parser.add_option('-l', '--list-projects',
                      action='store_true', dest='list_projects',
                      default=False,
                      help='List all projects and clients that can be compiled')
    parser.add_option('-a', '--compile-all',
                      action='store_true', dest='compile_all',
                      default=False,
                      help='Compile all available projects and clients')
    parser.add_option('-c', '--compile',
                      dest='compile_list', action='store',
                      help='List of clients to compiled (e.g. -c "x.X c.C")')
    parser.add_option('-e', '--extra-args',
                      dest='extra_args', action='store',
                      default='',
                      help='Extra arguments to pass to java')
    parser.add_option('-d', '--no-install', dest='install_client',
                      action='store_false', default=True,
                      help='Do not install the clients just compile them')
    options, args = parser.parse_args()

    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(0)
    elif options.list_projects:
        print_projects()
        sys.exit(0)
    elif options.compile_all and options.compile_list:
        logging.error('Options -c and -a are mutually exclusive')
        parser.print_help()
        sys.exit(1)

    failed_clients = []
    if options.compile_all:
        failed_clients = compile_all_projects(options.extra_args)
    elif options.compile_list:
        for client in options.compile_list.split():
            if not compile_and_install_client(client, options.extra_args,
                                              options.install_client):
                failed_clients.append(client)

    if os.path.exists(_TMP_COMPILE_DIR):
        shutil.rmtree(_TMP_COMPILE_DIR)

    if failed_clients:
        logging.error('The following clients failed: %s',
                      '\n'.join(failed_clients))
        sys.exit(1)


if __name__ == '__main__':
    main()
