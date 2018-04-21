import configparser
import html.parser
import logging
import os
import urllib

from autotest.client import os_dep, utils

try:
    import koji
    KOJI_INSTALLED = True
except ImportError:
    KOJI_INSTALLED = False

DEFAULT_KOJI_TAG = None


class KojiDirIndexParser(html.parser.HTMLParser):

    '''
    Parser for HTML directory index pages, specialized to look for RPM links
    '''

    def __init__(self):
        '''
        Initializes a new KojiDirListParser instance
        '''
        html.parser.HTMLParser.__init__(self)
        self.package_file_names = []

    def handle_starttag(self, tag, attrs):
        '''
        Handle tags during the parsing

        This just looks for links ('a' tags) for files ending in .rpm
        '''
        if tag == 'a':
            for k, v in attrs:
                if k == 'href' and v.endswith('.rpm'):
                    self.package_file_names.append(v)


class RPMFileNameInfo:

    '''
    Simple parser for RPM based on information present on the filename itself
    '''

    def __init__(self, filename):
        '''
        Initializes a new RpmInfo instance based on a filename
        '''
        self.filename = filename

    def get_filename_without_suffix(self):
        '''
        Returns the filename without the default RPM suffix
        '''
        assert self.filename.endswith('.rpm')
        return self.filename[0:-4]

    def get_filename_without_arch(self):
        '''
        Returns the filename without the architecture

        This also excludes the RPM suffix, that is, removes the leading arch
        and RPM suffix.
        '''
        wo_suffix = self.get_filename_without_suffix()
        arch_sep = wo_suffix.rfind('.')
        return wo_suffix[:arch_sep]

    def get_arch(self):
        '''
        Returns just the architecture as present on the RPM filename
        '''
        wo_suffix = self.get_filename_without_suffix()
        arch_sep = wo_suffix.rfind('.')
        return wo_suffix[arch_sep + 1:]

    def get_nvr_info(self):
        '''
        Returns a dictionary with the name, version and release components

        If koji is not installed, this returns None
        '''
        if not KOJI_INSTALLED:
            return None
        return koji.util.koji.parse_NVR(self.get_filename_without_arch())


class KojiClient(object):

    """
    Stablishes a connection with the build system, either koji or brew.

    This class provides convenience methods to retrieve information on packages
    and the packages themselves hosted on the build system. Packages should be
    specified in the KojiPgkSpec syntax.
    """

    CMD_LOOKUP_ORDER = ['/usr/bin/brew', '/usr/bin/koji']

    CONFIG_MAP = {'/usr/bin/brew': '/etc/brewkoji.conf',
                  '/usr/bin/koji': '/etc/koji.conf'}

    def __init__(self, cmd=None):
        """
        Verifies whether the system has koji or brew installed, then loads
        the configuration file that will be used to download the files.

        :type cmd: string
        :param cmd: Optional command name, either 'brew' or 'koji'. If not
                set, get_default_command() is used and to look for
                one of them.
        :raise: ValueError
        """
        if not KOJI_INSTALLED:
            raise ValueError('No koji/brew installed on the machine')

        # Instance variables used by many methods
        self.command = None
        self.config = None
        self.config_options = {}
        self.session = None

        # Set koji command or get default
        if cmd is None:
            self.command = self.get_default_command()
        else:
            self.command = cmd

        # Check koji command
        if not self.is_command_valid():
            raise ValueError('Koji command "%s" is not valid' % self.command)

        # Assuming command is valid, set configuration file and read it
        self.config = self.CONFIG_MAP[self.command]
        self.read_config()

        # Setup koji session
        server_url = self.config_options['server']
        session_options = self.get_session_options()
        self.session = koji.ClientSession(server_url,
                                          session_options)

    def read_config(self, check_is_valid=True):
        '''
        Reads options from the Koji configuration file

        By default it checks if the koji configuration is valid

        :type check_valid: boolean
        :param check_valid: whether to include a check on the configuration
        :raise: ValueError
        :return: None
        '''
        if check_is_valid:
            if not self.is_config_valid():
                raise ValueError('Koji config "%s" is not valid' % self.config)

        config = configparser.ConfigParser()
        config.read(self.config)

        basename = os.path.basename(self.command)
        for name, value in config.items(basename):
            self.config_options[name] = value

    def get_session_options(self):
        '''
        Filter only options necessary for setting up a cobbler client session

        :return: only the options used for session setup
        '''
        session_options = {}
        for name, value in self.config_options.items():
            if name in ('user', 'password', 'debug_xmlrpc', 'debug'):
                session_options[name] = value
        return session_options

    def is_command_valid(self):
        '''
        Checks if the currently set koji command is valid

        :return: True or False
        '''
        koji_command_ok = True

        if not os.path.isfile(self.command):
            logging.error('Koji command "%s" is not a regular file',
                          self.command)
            koji_command_ok = False

        if not os.access(self.command, os.X_OK):
            logging.warn('Koji command "%s" is not executable: this is '
                         'not fatal but indicates an unexpected situation',
                         self.command)

        if self.command not in self.CONFIG_MAP.keys():
            logging.error('Koji command "%s" does not have a configuration '
                          'file associated to it', self.command)
            koji_command_ok = False

        return koji_command_ok

    def is_config_valid(self):
        '''
        Checks if the currently set koji configuration is valid

        :return: True or False
        '''
        koji_config_ok = True

        if not os.path.isfile(self.config):
            logging.error('Koji config "%s" is not a regular file', self.config)
            koji_config_ok = False

        if not os.access(self.config, os.R_OK):
            logging.error('Koji config "%s" is not readable', self.config)
            koji_config_ok = False

        config = configparser.ConfigParser()
        config.read(self.config)
        basename = os.path.basename(self.command)
        if not config.has_section(basename):
            logging.error('Koji configuration file "%s" does not have a '
                          'section "%s", named after the base name of the '
                          'currently set koji command "%s"', self.config,
                          basename, self.command)
            koji_config_ok = False

        return koji_config_ok

    def get_default_command(self):
        '''
        Looks up for koji or brew "binaries" on the system

        Systems with plain koji usually don't have a brew cmd, while systems
        with koji, have *both* koji and brew utilities. So we look for brew
        first, and if found, we consider that the system is configured for
        brew. If not, we consider this is a system with plain koji.

        :return: either koji or brew command line executable path, or None
        '''
        koji_command = None
        for command in self.CMD_LOOKUP_ORDER:
            if os.path.isfile(command):
                koji_command = command
                break
            else:
                koji_command_basename = os.path.basename(command)
                try:
                    koji_command = os_dep.command(koji_command_basename)
                    break
                except ValueError:
                    pass
        return koji_command

    def get_pkg_info(self, pkg):
        '''
        Returns information from Koji on the package

        :type pkg: KojiPkgSpec
        :param pkg: information about the package, as a KojiPkgSpec instance

        :return: information from Koji about the specified package
        '''
        info = {}
        if pkg.build is not None:
            info = self.session.getBuild(int(pkg.build))
        elif pkg.tag is not None and pkg.package is not None:
            builds = self.session.listTagged(pkg.tag,
                                             latest=True,
                                             inherit=True,
                                             package=pkg.package)
            if builds:
                info = builds[0]
        return info

    def is_pkg_valid(self, pkg):
        '''
        Checks if this package is altogether valid on Koji

        This verifies if the build or tag specified in the package
        specification actually exist on the Koji server

        :return: True or False
        '''
        valid = True
        if pkg.build:
            if not self.is_pkg_spec_build_valid(pkg):
                valid = False
        elif pkg.tag:
            if not self.is_pkg_spec_tag_valid(pkg):
                valid = False
        else:
            valid = False
        return valid

    def is_pkg_spec_build_valid(self, pkg):
        '''
        Checks if build is valid on Koji

        :param pkg: a Pkg instance
        '''
        if pkg.build is not None:
            info = self.session.getBuild(int(pkg.build))
            if info:
                return True
        return False

    def is_pkg_spec_tag_valid(self, pkg):
        '''
        Checks if tag is valid on Koji

        :type pkg: KojiPkgSpec
        :param pkg: a package specification
        '''
        if pkg.tag is not None:
            tag = self.session.getTag(pkg.tag)
            if tag:
                return True
        return False

    def get_pkg_rpm_info(self, pkg, arch=None):
        '''
        Returns a list of information on the RPM packages found on koji

        :type pkg: KojiPkgSpec
        :param pkg: a package specification
        :type arch: string
        :param arch: packages built for this architecture, but also including
                architecture independent (noarch) packages
        '''
        if arch is None:
            arch = utils.get_arch()
        rpms = []
        info = self.get_pkg_info(pkg)
        if info:
            rpms = self.session.listRPMs(buildID=info['id'],
                                         arches=[arch, 'noarch'])
            if pkg.subpackages:
                rpms = [d for d in rpms if d['name'] in pkg.subpackages]
        return rpms

    def get_pkg_rpm_names(self, pkg, arch=None):
        '''
        Gets the names for the RPM packages specified in pkg

        :type pkg: KojiPkgSpec
        :param pkg: a package specification
        :type arch: string
        :param arch: packages built for this architecture, but also including
                architecture independent (noarch) packages
        '''
        if arch is None:
            arch = utils.get_arch()
        rpms = self.get_pkg_rpm_info(pkg, arch)
        return [rpm['name'] for rpm in rpms]

    def get_pkg_rpm_file_names(self, pkg, arch=None):
        '''
        Gets the file names for the RPM packages specified in pkg

        :type pkg: KojiPkgSpec
        :param pkg: a package specification
        :type arch: string
        :param arch: packages built for this architecture, but also including
                architecture independent (noarch) packages
        '''
        if arch is None:
            arch = utils.get_arch()
        rpm_names = []
        rpms = self.get_pkg_rpm_info(pkg, arch)
        for rpm in rpms:
            arch_rpm_name = koji.pathinfo.rpm(rpm)
            rpm_name = os.path.basename(arch_rpm_name)
            rpm_names.append(rpm_name)
        return rpm_names

    def get_pkg_base_url(self):
        '''
        Gets the base url for packages in Koji
        '''
        if self.config_options.has_key('pkgurl'):
            return self.config_options['pkgurl']
        else:
            return "%s/%s" % (self.config_options['topurl'],
                              'packages')

    def get_scratch_base_url(self):
        '''
        Gets the base url for scratch builds in Koji
        '''
        one_level_up = os.path.dirname(self.get_pkg_base_url())
        return "%s/%s" % (one_level_up, 'scratch')

    def get_pkg_urls(self, pkg, arch=None):
        '''
        Gets the urls for the packages specified in pkg

        :type pkg: KojiPkgSpec
        :param pkg: a package specification
        :type arch: string
        :param arch: packages built for this architecture, but also including
                architecture independent (noarch) packages
        '''
        info = self.get_pkg_info(pkg)
        rpms = self.get_pkg_rpm_info(pkg, arch)
        rpm_urls = []
        base_url = self.get_pkg_base_url()

        for rpm in rpms:
            rpm_name = koji.pathinfo.rpm(rpm)
            url = ("%s/%s/%s/%s/%s" % (base_url,
                                       info['package_name'],
                                       info['version'], info['release'],
                                       rpm_name))
            rpm_urls.append(url)
        return rpm_urls

    def get_pkgs(self, pkg, dst_dir, arch=None):
        '''
        Download the packages

        :type pkg: KojiPkgSpec
        :param pkg: a package specification
        :type dst_dir: string
        :param dst_dir: the destination directory, where the downloaded
                packages will be saved on
        :type arch: string
        :param arch: packages built for this architecture, but also including
                architecture independent (noarch) packages
        '''
        rpm_urls = self.get_pkg_urls(pkg, arch)
        for url in rpm_urls:
            utils.get_file(url,
                           os.path.join(dst_dir, os.path.basename(url)))

    def get_scratch_pkg_urls(self, pkg, arch=None):
        '''
        Gets the urls for the scratch packages specified in pkg

        :type pkg: KojiScratchPkgSpec
        :param pkg: a scratch package specification
        :type arch: string
        :param arch: packages built for this architecture, but also including
                architecture independent (noarch) packages
        '''
        rpm_urls = []

        if arch is None:
            arch = utils.get_arch()
        arches = [arch, 'noarch']

        index_url = "%s/%s/task_%s" % (self.get_scratch_base_url(),
                                       pkg.user,
                                       pkg.task)
        index_parser = KojiDirIndexParser()
        index_parser.feed(urllib.urlopen(index_url).read())

        if pkg.subpackages:
            for p in pkg.subpackages:
                for pfn in index_parser.package_file_names:
                    r = RPMFileNameInfo(pfn)
                    info = r.get_nvr_info()
                    if (p == info['name'] and
                            r.get_arch() in arches):
                        rpm_urls.append("%s/%s" % (index_url, pfn))
        else:
            for pfn in index_parser.package_file_names:
                if (RPMFileNameInfo(pfn).get_arch() in arches):
                    rpm_urls.append("%s/%s" % (index_url, pfn))

        return rpm_urls

    def get_scratch_pkgs(self, pkg, dst_dir, arch=None):
        '''
        Download the packages from a scratch build

        :type pkg: KojiScratchPkgSpec
        :param pkg: a scratch package specification
        :type dst_dir: string
        :param dst_dir: the destination directory, where the downloaded
                packages will be saved on
        :type arch: string
        :param arch: packages built for this architecture, but also including
                architecture independent (noarch) packages
        '''
        rpm_urls = self.get_scratch_pkg_urls(pkg, arch)
        for url in rpm_urls:
            utils.get_file(url,
                           os.path.join(dst_dir, os.path.basename(url)))


def set_default_koji_tag(tag):
    '''
    Sets the default tag that will be used
    '''
    global DEFAULT_KOJI_TAG
    DEFAULT_KOJI_TAG = tag


def get_default_koji_tag():
    return DEFAULT_KOJI_TAG


class KojiPkgSpec(object):

    '''
    A package specification syntax parser for Koji

    This holds information on either tag or build, and packages to be fetched
    from koji and possibly installed (features external do this class).

    New objects can be created either by providing information in the textual
    format or by using the actual parameters for tag, build, package and sub-
    packages. The textual format is useful for command line interfaces and
    configuration files, while using parameters is better for using this in
    a programatic fashion.

    The following sets of examples are interchangeable. Specifying all packages
    part of build number 1000:

        >>> from kvm_utils import KojiPkgSpec
        >>> pkg = KojiPkgSpec('1000')

        >>> pkg = KojiPkgSpec(build=1000)

    Specifying only a subset of packages of build number 1000:

        >>> pkg = KojiPkgSpec('1000:kernel,kernel-devel')

        >>> pkg = KojiPkgSpec(build=1000,
                              subpackages=['kernel', 'kernel-devel'])

    Specifying the latest build for the 'kernel' package tagged with 'dist-f14':

        >>> pkg = KojiPkgSpec('dist-f14:kernel')

        >>> pkg = KojiPkgSpec(tag='dist-f14', package='kernel')

    Specifying the 'kernel' package using the default tag:

        >>> kvm_utils.set_default_koji_tag('dist-f14')
        >>> pkg = KojiPkgSpec('kernel')

        >>> pkg = KojiPkgSpec(package='kernel')

    Specifying the 'kernel' package using the default tag:

        >>> kvm_utils.set_default_koji_tag('dist-f14')
        >>> pkg = KojiPkgSpec('kernel')

        >>> pkg = KojiPkgSpec(package='kernel')

    If you do not specify a default tag, and give a package name without an
    explicit tag, your package specification is considered invalid:

        >>> print(kvm_utils.get_default_koji_tag())
        None
        >>> print(kvm_utils.KojiPkgSpec('kernel').is_valid())
        False

        >>> print(kvm_utils.KojiPkgSpec(package='kernel').is_valid())
        False
    '''

    SEP = ':'

    def __init__(self, text='', tag=None, build=None,
                 package=None, subpackages=[]):
        '''
        Instantiates a new KojiPkgSpec object

        :type text: string
        :param text: a textual representation of a package on Koji that
                will be parsed
        :type tag: string
        :param tag: a koji tag, example: Fedora-14-RELEASE
                (see U{http://fedoraproject.org/wiki/Koji#Tags_and_Targets})
        :type build: number
        :param build: a koji build, example: 1001
                (see U{http://fedoraproject.org/wiki/Koji#Koji_Architecture})
        :type package: string
        :param package: a koji package, example: python
                (see U{http://fedoraproject.org/wiki/Koji#Koji_Architecture})
        :type subpackages: list of strings
        :param subpackages: a list of package names, usually a subset of
                the RPM packages generated by a given build
        '''

        # Set to None to indicate 'not set' (and be able to use 'is')
        self.tag = None
        self.build = None
        self.package = None
        self.subpackages = []

        self.default_tag = None

        # Textual representation takes precedence (most common use case)
        if text:
            self.parse(text)
        else:
            self.tag = tag
            self.build = build
            self.package = package
            self.subpackages = subpackages

        # Set the default tag, if set, as a fallback
        if not self.build and not self.tag:
            default_tag = get_default_koji_tag()
            if default_tag is not None:
                self.tag = default_tag

    def parse(self, text):
        '''
        Parses a textual representation of a package specification

        :type text: string
        :param text: textual representation of a package in koji
        '''
        parts = text.count(self.SEP) + 1
        if parts == 1:
            if text.isdigit():
                self.build = text
            else:
                self.package = text
        elif parts == 2:
            part1, part2 = text.split(self.SEP)
            if part1.isdigit():
                self.build = part1
                self.subpackages = part2.split(',')
            else:
                self.tag = part1
                self.package = part2
        elif parts >= 3:
            # Instead of erroring on more arguments, we simply ignore them
            # This makes the parser suitable for future syntax additions, such
            # as specifying the package architecture
            part1, part2, part3 = text.split(self.SEP)[0:3]
            self.tag = part1
            self.package = part2
            self.subpackages = part3.split(',')

    def _is_invalid_neither_tag_or_build(self):
        '''
        Checks if this package is invalid due to not having either a valid
        tag or build set, that is, both are empty.

        :return: True if this is invalid and False if it's valid
        '''
        return (self.tag is None and self.build is None)

    def _is_invalid_package_but_no_tag(self):
        '''
        Checks if this package is invalid due to having a package name set
        but tag or build set, that is, both are empty.

        :return: True if this is invalid and False if it's valid
        '''
        return (self.package and not self.tag)

    def _is_invalid_subpackages_but_no_main_package(self):
        '''
        Checks if this package is invalid due to having a tag set (this is Ok)
        but specifying subpackage names without specifying the main package
        name.

        Specifying subpackages without a main package name is only valid when
        a build is used instead of a tag.

        :return: True if this is invalid and False if it's valid
        '''
        return (self.tag and self.subpackages and not self.package)

    def is_valid(self):
        '''
        Checks if this package specification is valid.

        Being valid means that it has enough and not conflicting information.
        It does not validate that the packages specified actually existe on
        the Koji server.

        :return: True or False
        '''
        if self._is_invalid_neither_tag_or_build():
            return False
        elif self._is_invalid_package_but_no_tag():
            return False
        elif self._is_invalid_subpackages_but_no_main_package():
            return False

        return True

    def describe_invalid(self):
        '''
        Describes why this is not valid, in a human friendly way
        '''
        if self._is_invalid_neither_tag_or_build():
            return ('neither a tag nor a build were set, one of them '
                    'must be set')
        elif self._is_invalid_package_but_no_tag():
            return 'package name specified but no tag is set'
        elif self._is_invalid_subpackages_but_no_main_package():
            return 'subpackages specified but no main package is set'

        return 'unkwown reason, seems to be valid'

    def describe(self):
        '''
        Describe this package specification, in a human friendly way

        :return: package specification description
        '''
        if self.is_valid():
            description = ''
            if not self.subpackages:
                description += 'all subpackages from %s ' % self.package
            else:
                description += ('only subpackage(s) %s from package %s ' %
                                (', '.join(self.subpackages), self.package))

            if self.build:
                description += 'from build %s' % self.build
            elif self.tag:
                description += 'tagged with %s' % self.tag
            else:
                raise ValueError('neither build or tag is set')

            return description
        else:
            return ('Invalid package specification: %s' %
                    self.describe_invalid())

    def to_text(self):
        '''
        Return the textual representation of this package spec

        The output should be consumable by parse() and produce the same
        package specification.

        We find that it's acceptable to put the currently set default tag
        as the package explicit tag in the textual definition for completeness.

        :return: package specification in a textual representation
        '''
        default_tag = get_default_koji_tag()

        if self.build:
            if self.subpackages:
                return "%s:%s" % (self.build, ",".join(self.subpackages))
            else:
                return "%s" % self.build

        elif self.tag:
            if self.subpackages:
                return "%s:%s:%s" % (self.tag, self.package,
                                     ",".join(self.subpackages))
            else:
                return "%s:%s" % (self.tag, self.package)

        elif default_tag is not None:
            # neither build or tag is set, try default_tag as a fallback
            if self.subpackages:
                return "%s:%s:%s" % (default_tag, self.package,
                                     ",".join(self.subpackages))
            else:
                return "%s:%s" % (default_tag, self.package)
        else:
            raise ValueError('neither build or tag is set')

    def __repr__(self):
        return ("<KojiPkgSpec tag=%s build=%s pkg=%s subpkgs=%s>" %
                (self.tag, self.build, self.package,
                 ", ".join(self.subpackages)))


class KojiScratchPkgSpec(object):

    '''
    A package specification syntax parser for Koji scratch builds

    This holds information on user, task and subpackages to be fetched
    from koji and possibly installed (features external do this class).

    New objects can be created either by providing information in the textual
    format or by using the actual parameters for user, task and subpackages.
    The textual format is useful for command line interfaces and configuration
    files, while using parameters is better for using this in a programatic
    fashion.

    This package definition has a special behaviour: if no subpackages are
    specified, all packages of the chosen architecture (plus noarch packages)
    will match.

    The following sets of examples are interchangeable. Specifying all packages
    from a scratch build (whose task id is 1000) sent by user jdoe:

        >>> from kvm_utils import KojiScratchPkgSpec
        >>> pkg = KojiScratchPkgSpec('jdoe:1000')

        >>> pkg = KojiScratchPkgSpec(user=jdoe, task=1000)

    Specifying some packages from a scratch build whose task id is 1000, sent
    by user jdoe:

        >>> pkg = KojiScratchPkgSpec('jdoe:1000:kernel,kernel-devel')

        >>> pkg = KojiScratchPkgSpec(user=jdoe, task=1000,
                                     subpackages=['kernel', 'kernel-devel'])
    '''

    SEP = ':'

    def __init__(self, text='', user=None, task=None, subpackages=[]):
        '''
        Instantiates a new KojiScratchPkgSpec object

        :type text: string
        :param text: a textual representation of a scratch build on Koji that
                will be parsed
        :type task: number
        :param task: a koji task id, example: 1001
        :type subpackages: list of strings
        :param subpackages: a list of package names, usually a subset of
                the RPM packages generated by a given build
        '''
        # Set to None to indicate 'not set' (and be able to use 'is')
        self.user = None
        self.task = None
        self.subpackages = []

        # Textual representation takes precedence (most common use case)
        if text:
            self.parse(text)
        else:
            self.user = user
            self.task = task
            self.subpackages = subpackages

    def parse(self, text):
        '''
        Parses a textual representation of a package specification

        :type text: string
        :param text: textual representation of a package in koji
        '''
        parts = text.count(self.SEP) + 1
        if parts == 1:
            raise ValueError('KojiScratchPkgSpec requires a user and task id')
        elif parts == 2:
            self.user, self.task = text.split(self.SEP)
        elif parts >= 3:
            # Instead of erroring on more arguments, we simply ignore them
            # This makes the parser suitable for future syntax additions, such
            # as specifying the package architecture
            part1, part2, part3 = text.split(self.SEP)[0:3]
            self.user = part1
            self.task = part2
            self.subpackages = part3.split(',')

    def __repr__(self):
        return ("<KojiScratchPkgSpec user=%s task=%s subpkgs=%s>" %
                (self.user, self.task, ", ".join(self.subpackages)))
