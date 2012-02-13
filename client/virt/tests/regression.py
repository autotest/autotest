import ConfigParser, sys, commands, os
import analyzer

def compare(testname, olddir, curdir, config_file='perf.conf', output_dir=""):
    config = ConfigParser.ConfigParser()
    config.read(config_file)

    result_nfs = config.get("server", "result_nfs")
    result_mntdir = config.get("server", "result_mntdir")
    result_dir = config.get(testname, "result_dir")
    result_file_pattern = config.get(testname, "result_file_pattern")

    def search_files(dir):
        cmd = 'find %s|grep %s|grep "%s/%s"' % (dir,
           testname, result_dir, result_file_pattern)
        return commands.getoutput(cmd)

    if not os.path.isdir(result_mntdir):
        os.mkdir(result_mntdir)
    commands.getoutput("mount %s %s" % (result_nfs, result_mntdir))

    if not os.path.isabs(olddir):
        olddir = result_mntdir + olddir
    oldlist = search_files(olddir)
    newlist = search_files(curdir)
    if oldlist != "" or newlist != "":
        analyzer.analyze(oldlist, newlist, output_dir)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print 'Usage: python %s $testname $dir1 $dir2 $configfile' % sys.argv[0]
        sys.exit(1)
    compare(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
