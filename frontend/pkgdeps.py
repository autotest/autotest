"""
List of distribution package dependencies for the frontend, that is,
packages needed for running the AFE and TKO servers
"""


FEDORA_REDHAT_PKGS = [
    'Django',
    'Django-south',
    'MySQL-python',
    'git',
    'httpd',
    'java-devel',
    'mod_wsgi',
    'mysql-server',
    'numpy',
    'policycoreutils-python',
    'python-django',
    'python-atfork',
    'python-crypto',
    'python-httplib2',
    'python-imaging',
    'python-matplotlib',
    'python-paramiko',
    'selinux-policy',
    'selinux-policy-targeted',
    'unzip',
    'urw-fonts',
    'wget',
    'protobuf-compiler',
    'protobuf-python',
    'passwd',
    'pylint']


UBUNTU_PKGS = [
    'apache2-mpm-prefork',
    'git',
    'gnuplot',
    'libapache2-mod-wsgi',
    'libgwt-dev-java',
    'makepasswd',
    'mysql-server',
    'openjdk-7-jre-headless',
    'python-crypto',
    'python-django',
    'python-django-south',
    'python-httplib2',
    'python-imaging',
    'python-matplotlib',
    'python-mysqldb',
    'python-numpy',
    'python-paramiko',
    'python-setuptools',
    'python-simplejson',
    'unzip',
    'wget',
    'protobuf-compiler',
    'python-protobuf',
    'pylint']


PKG_DEPS = {'Fedora' : FEDORA_REDHAT_PKGS,
            'Red Hat' : FEDORA_REDHAT_PKGS,
            'Ubuntu' : UBUNTU_PKGS}
