import re, os,logging,shutil
from autotest.client import utils, test
from autotest.client.shared import git, software_manager, error

class SCSIUtilNotAvailable(Exception):
    def __init__(self, name):
        self.util_name = name

    def __str__(self):
        return "%s not installed" % self.util_name

class UnknownSourceType(Exception):
   def __init__(self,source):
       self.source = source

   def __str__(self):
       return "Unknown source type: %s" % self.source

class scsi_testsuit(test.test):
    version = 1
    scsi_testsuite_config = "/etc/scsi-testsuite.config"


    def warmup(self,source_type, source_location,disk_addr,**kwargs):
        if source_type == "tar":
            tarball = utils.unmap_url(self.bindir, source_location,self.tmpdir)
            self.repodir = os.path.join(self.tmpdir,"testsuit")
            utils.extract_tarball_to_dir(tarball,self.repodir)
        elif source_type == "git":
            self.repodir = git.get_repo(source_location)
        else:
            raise UnknownSourceType(source_type)

        sm = software_manager.SoftwareManager()
        if not os.access('/usr/bin/sg_raw',os.X_OK):
            logging.debug("sg3_utils missing - trying to install")
            pckg = sm.provides('/usr/bin/sg_raw')
            if pckg is None:
                raise SCSIUtilNotAvailable("sg_raw")
            else:
                sm.install(pckg)

        self.devname = ""
        if disk_addr[0] == "scsi":
	    if not os.access('/usr/bin/lsscsi',os.X_OK):
                logging.debug("lsscsi missing - trying to install")
                pckg = sm.provides('/usr/bin/lsscsi')
                if pckg is None:
                    raise SCSIUtilNotAvailable("lscssi")
                else:
                    sm.install(pckg)

            addr = (disk_addr[1]["host"],
                    disk_addr[1]["channel"],
                    disk_addr[1]["target"],
                    disk_addr[1]["lun"])

            self.devname = utils.system_output(
                           "lsscsi %d %d %d %d | sed -n 's,.*/dev,/dev,p' " % 
                           addr)

        elif disk_addr[0] == "serial":
            disklist = os.listdir("/dev/disk/by-id/")
            for diskfile in disklist:
               if re.match("scsi-.*%s$" % disk_addr[1],diskfile) is not None:
                  self.devname = os.path.join("/dev/disk/by-id",diskfile)
                  break
        elif disk_addr[0] == "file":
            if os.access(disk_addr[1],os.F_OK) == True:
                self.devname = disk_addr[1]

        if self.devname == "":
            output = utils.system_output("lsscsi")
            logging.debug(output)
            raise error.TestFail("Disk not found, cannot execute tests")

        try:
            cf = open(self.scsi_testsuite_config,"w")
            cf.write("export TEST_DEV=%s" % self.devname)
            cf.close()
        except IOError:
            logging.warning("Can't write configuration file. Using defaults")
        

    def run_once(self,run_tests,**kwargs):
        os.chdir(self.repodir)

        failed = 0
        run = 0
        for testname in run_tests:
            result = utils.run("./check %s" % testname,ignore_status=True)
            run = run  + 1
            shutil.copy(
                   os.path.join(self.repodir,"%s.out" % testname),
                   os.path.join(self.resultsdir,"%s.out" % testname))
            if result.exit_status == 0:
                logging.info("Test %s SUCCEED" % testname)
                self.write_attr_keyval({testname:"Succeed"})
            else:
                failed = failed + 1
                shutil.copy(
                   os.path.join(self.repodir,"%s.out.bad" % testname),
                   os.path.join(self.resultsdir,"%s.out.bad" % testname))
                logging.info("Test %s FAILED" % testname)
                self.write_attr_keyval({testname:"Failed"})

        if failed > 0:
           raise error.TestFail("Failed %d of %d tests" % (failed, run))

    def cleanup(self):
        shutil.rmtree(self.repodir)
        if os.access(self.scsi_testsuite_config,os.F_OK):
            os.remove(self.scsi_testsuite_config)
