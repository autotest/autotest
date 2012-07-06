import os, logging
from autotest.client import test
from autotest.client import utils
from autotest.client.shared import git, error, software_manager
from autotest.client.virt import virt_utils


class kernelinstall(test.test):
    version = 1

    def _kernel_install_rpm(self, rpm_file, kernel_deps_rpms=None,
                            need_reboot=True):
        """
        Install kernel rpm package.
        The rpm packages should be a url or put in this test's
        directory (client/test/kernelinstall)
        """
        if kernel_deps_rpms:
            logging.info("Installing kernel dependencies.")
            if isinstance(kernel_deps_rpms, list):
                kernel_deps_rpms = " ".join(kernel_deps_rpms)
            utils.run('rpm -U --force %s' % kernel_deps_rpms)

        dst = os.path.join("/tmp", os.path.basename(rpm_file))
        knl = utils.get_file(rpm_file, dst)
        kernel = self.job.kernel(knl)
        logging.info("Installing kernel %s", rpm_file)
        kernel.install(install_vmlinux=False)

        if need_reboot:
            kernel.boot()
        else:
            kernel.add_to_bootloader()


    def _kernel_install_koji(self, koji_tag, package="kernel", dep_pkgs=None,
                             need_reboot=True):
        sm = software_manager.SoftwareManager()
        for utility in ['/usr/bin/koji', '/usr/bin/brew']:
            if not os.access(utility, os.X_OK):
                logging.debug("%s missing - trying to install", utility)
                pkg = sm.provides(utility)
                if pkg is not None:
                    sm.install(pkg)
                else:
                    logging.error("No %s available on software sources" %
                                  utility)
        # First, download packages via koji/brew
        c = virt_utils.KojiClient()
        deps_rpms = ""
        if dep_pkgs:
            for p in dep_pkgs.split():
                logging.info('Fetching kernel dependencies: %s', p)
                k_dep = virt_utils.KojiPkgSpec(tag=koji_tag, package=p,
                                                subpackages=[p])
                c.get_pkgs(k_dep, self.bindir)
                deps_rpms += " "
                deps_rpms += os.path.join(self.bindir,
                                         c.get_pkg_rpm_file_names(k_dep)[0])

        k = virt_utils.KojiPkgSpec(tag=koji_tag, package=package,
                                   subpackages=[package])

        c.get_pkgs(k, self.bindir)

        rpm_file = os.path.join(self.bindir, c.get_pkg_rpm_file_names(k)[0])

        # Then install kernel rpm packages.
        self._kernel_install_rpm(rpm_file, deps_rpms, need_reboot)


    def _kernel_install_src(self, base_tree, config, config_list=None,
                           patch_list=None, need_reboot=True):
        if not utils.is_url(base_tree):
            base_tree = os.path.join(self.bindir, base_tree)
        if not utils.is_url(config):
            config = os.path.join(self.bindir, config)
        kernel = self.job.kernel(base_tree, self.outputdir)
        if patch_list:
            patches = []
            for p in patch_list.split():
                # Make sure all the patches are in local.
                if not utils.is_url(p):
                    continue
                dst = os.path.join(self.bindir, os.path.basename(p))
                local_patch = utils.get_file(p, dst)
                patches.append(local_patch)
            kernel.patch(*patches)
        kernel.config(config, config_list)
        kernel.build()
        kernel.install()

        if need_reboot:
            kernel.boot()
        else:
            kernel.add_to_bootloader()


    def _kernel_install_git(self, repo, config, repo_base=None,
                            branch="master", commit=None, config_list=None,
                            patch_list=None, need_reboot=True):
        repodir = os.path.join("/tmp", 'kernel_src')
        repodir = git.get_repo(uri=repo, branch=branch,
                               destination_dir=repodir,
                               commit=commit, base_uri=repo_base)
        self._kernel_install_src(repodir, config, config_list, patch_list,
                                need_reboot)


    def execute(self, install_type="koji", params=None):
        need_reboot = params.get("need_reboot") == "yes"

        logging.info("Chose to install kernel through '%s', proceeding",
                     install_type)

        if install_type == "rpm":
            rpm_url = params.get("kernel_rpm_path")
            kernel_deps_rpms = params.get("kernel_deps_rpms", None)

            self._kernel_install_rpm(rpm_url, kernel_deps_rpms, need_reboot)
        elif install_type in ["koji", "brew"]:

            koji_tag = params.get("kernel_koji_tag")
            if not koji_tag:
                # Try to get brew tag if not set "kernel_koji_tag" parameter
                koji_tag = params.get("brew_tag")

            if not koji_tag:
                raise error.TestError("Could not find Koji/brew tag.")

            dep_pkgs = params.get("kernel_dep_pkgs", None)

            self._kernel_install_koji(koji_tag, "kernel", dep_pkgs,
                                      need_reboot)
        elif install_type == "git":
            repo = params.get('kernel_git_repo')
            repo_base = params.get('kernel_git_repo_base', None)
            branch = params.get('kernel_git_branch', "master")
            commit = params.get('kernel_git_commit', None)
            patch_list = params.get("kernel_patch_list", None)
            config = params.get('kernel_config')
            config_list = params.get("kernel_config_list", None)

            self._kernel_install_git(repo, config, repo_base, branch, commit,
                                     config_list, patch_list, need_reboot)
        elif install_type == "tar":
            src_pkg = params.get("kernel_src_pkg")
            config = params.get('kernel_config')
            patch_list = params.get("kernel_patch_list", None)

            self._kernel_install_src(src_pkg, config, None, patch_list,
                                     need_reboot)
        else:
            logging.error("Could not find '%s' method, "
                          "keep the current kernel.", install_type)
