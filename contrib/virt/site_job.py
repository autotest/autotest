import os, re, sys, pwd, time, socket, getpass
import inspect, new, logging, string, tempfile

from autotest_lib.cli import topic_common, action_common
from autotest_lib.cli import job
from autotest_lib.client.common_lib import logging_config
from autotest_lib.client.virt import virt_utils

logging_config.LoggingConfig().configure_logging(verbose=True)


class site_job(job.job):
    pass


class site_job_create(job.job_create):
    """
    Adds job manipulation including installing packages from brew
    """

    op_action = 'create'

    def __init__(self):
        super(site_job_create, self).__init__()
        self.parser.add_option('-T', '--template', action='store_true',
                               help='Control file is actually a template')
        self.parser.add_option('-x', '--extra-cartesian-config',
                               action='append',
                               help='Add extra configuration to the cartesian '
                               'config file')
        self.parser.add_option('--timestamp', action='store_true',
                               help='Add a timestamp to the name of the job')
        self.parser.add_option('--koji-arch', default='x86_64',
                               help='Default architecture for packages '
                               'that will be fetched from koji build. '
                               'This will be combined with "noarch".'
                               'This option is used to help to validate '
                               'packages from the job submitting machine.')
        self.parser.add_option('--koji-tag', help='Sets a default koji tag '
                               'for koji packages specified with --koji-pkg')
        self.parser.add_option('--koji-pkg', action='append',
                               help='Packages to add to host installation '
                               'based on koji build. This options may be '
                               'specified multiple times.')
        self.koji_client = None


    def parse(self):
        '''
        Parse options.

        If any brew options is specified, instantiate KojiDownloader
        '''
        (self.command_line_options,
         self.command_line_leftover) = super(site_job_create, self).parse()

        #
        # creating the new control file
        #
        if (self.command_line_options.template and
            self.command_line_options.control_file):
            generated_control_file = self._generate_control_file()
            self.data['control_file'] = open(generated_control_file).read()

        if self.command_line_options.koji_pkg:
            if self.koji_client is None:
                self.koji_client = virt_utils.KojiClient()

        return (self.command_line_options, self.command_line_leftover)


    def _process_options(self):
        '''
        Process all options given on command line
        '''
        all_options_valid = True

        self._set_koji_tag()
        if not self._check_koji_packages():
            all_options_valid = False

        return all_options_valid


    def _set_koji_tag(self):
        '''
        Sets the default koji tag.

        Configuration item on file is: koji_tag
        '''
        if self.command_line_options.koji_tag is not None:
            virt_utils.set_default_koji_tag(self.command_line_options.koji_tag)


    def _check_koji_packages(self):
        '''
        Check if packages specification are valid and exist on koji/brew

        Configuration item on file is: koji_pkgs
        '''
        all_packages_found = True
        if self.command_line_options.koji_pkg is not None:
            logging.debug('Checking koji packages specification')
            for pkg_spec_text in self.command_line_options.koji_pkg:
                pkg_spec = virt_utils.KojiPkgSpec(pkg_spec_text)

                if not (pkg_spec.is_valid() and
                        self.koji_client.is_pkg_valid(pkg_spec)):
                    logging.error('Koji package spec is not valid, skipping: '
                                  '%s' % pkg_spec)
                    all_packages_found = False
                else:
                    rpms = self.koji_client.get_pkg_rpm_info(
                        pkg_spec,
                        self.command_line_options.koji_arch)
                    for subpackage in pkg_spec.subpackages:
                        if subpackage not in [rpm['name'] for rpm in rpms]:
                            logging.error('Package specified but not found in '
                                          'koji: %s' % subpackage)
                            all_packages_found = False

                    rpms = ", ".join(rpm['nvr'] for rpm in rpms)
                    logging.debug('Koji package spec is valid')
                    logging.debug('Koji packages to be fetched and installed: '
                                  '%s' % rpms)

        return all_packages_found

    def _generate_job_config(self):
        '''
        Converts all options given on the command line to config file syntax
        '''
        extra = []
        if self.command_line_options.extra_cartesian_config:
            extra += self.command_line_options.extra_cartesian_config

        if self.command_line_options.koji_tag:
            extra.append("koji_tag = %s" % self.command_line_options.koji_tag)

        if self.command_line_options.koji_pkg:
            koji_pkgs = []
            for koji_pkg in self.command_line_options.koji_pkg:
                koji_pkgs.append('"%s"' % koji_pkg)
            extra.append("koji_pkgs = [%s]" % ', '.join(koji_pkgs))

        # add quotes...
        extra = ["'%s'" % e for e in extra]
        # ... and return as string that will be eval'd as a Python list
        return "[%s]" % ', '.join(extra)


    def _generate_control_file(self):
        '''
        Generates a controle file from a template
        '''
        custom_job_cfg = self._generate_job_config()
        input_file = self.command_line_options.control_file
        logging.debug('Generating control file from template: %s' % input_file)
        template = string.Template(open(input_file).read())
        output_fd, path = tempfile.mkstemp(prefix='atest_control_', dir='/tmp')
        logging.debug('Generated control file to be saved at: %s' % path)
        parameters_dict = {"custom_job_cfg": custom_job_cfg}
        control_file_text = template.substitute(parameters_dict)
        os.write(output_fd, control_file_text)
        os.close(output_fd)
        return path


    def execute(self):
        if not self._process_options():
            self.generic_error('Some command line options validation failed. '
                               'Aborting job creation.')
            return

        #
        # add timestamp to the jobname
        #
        if self.command_line_options.timestamp:
            logging.debug("Adding timestamp to jobname")
            timestamp = time.strftime(" %m-%d-%Y %H:%M:%S", time.localtime())
            self.jobname += timestamp
            self.data['name'] = self.jobname

        execute_results = super(site_job_create, self).execute()
        self.output(execute_results)


for cls in [getattr(job, n) for n in dir(job) if not n.startswith("_")]:
    if not inspect.isclass(cls):
        continue
    cls_name = cls.__name__
    site_cls_name = 'site_' + cls_name
    if hasattr(sys.modules[__name__], site_cls_name):
        continue
    bases = (site_job, cls)
    members = {'__doc__': cls.__doc__}
    site_cls = new.classobj(site_cls_name, bases, members)
    setattr(sys.modules[__name__], site_cls_name, site_cls)
