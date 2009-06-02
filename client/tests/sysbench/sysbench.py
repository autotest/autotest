import os, time, re, pwd
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class sysbench(test.test):
    version = 1

    def initialize(self):
        self.job.require_gcc()
        self.results = []

    # http://osdn.dl.sourceforge.net/sourceforge/sysbench/sysbench-0.4.8.tar.gz
    def setup(self, tarball = 'sysbench-0.4.8.tar.bz2'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        self.job.setup_dep(['pgsql', 'mysql'])

        os.chdir(self.srcdir)

        pgsql_dir = os.path.join(self.autodir, 'deps/pgsql/pgsql')
        mysql_dir = os.path.join(self.autodir, 'deps/mysql/mysql')

        # configure wants to get at pg_config, so add its path
        utils.system(
            'PATH=%s/bin:$PATH ./configure --with-mysql=%s --with-pgsql'
            % (pgsql_dir, mysql_dir))
        utils.system('make -j %d' % utils.count_cpus())


    def run_once(self, db_type = 'pgsql', build = 1, \
                    num_threads = utils.count_cpus(), max_time = 60, \
                    read_only = 0, args = ''):
        plib = os.path.join(self.autodir, 'deps/pgsql/pgsql/lib')
        mlib = os.path.join(self.autodir, 'deps/mysql/mysql/lib/mysql')
        ld_path = utils.prepend_path(plib,
            utils.environ('LD_LIBRARY_PATH'))
        ld_path = utils.prepend_path(mlib, ld_path)
        os.environ['LD_LIBRARY_PATH'] = ld_path

        # The databases don't want to run as root so run them as nobody
        self.dbuser = 'nobody'
        self.dbuid = pwd.getpwnam(self.dbuser)[2]
        self.sudo = 'sudo -u ' + self.dbuser + ' '

        # Check for nobody user
        try:
            utils.system(self.sudo + '/bin/true')
        except:
            raise error.TestError('Unable to run as nobody')

        if (db_type == 'pgsql'):
            self.execute_pgsql(build, num_threads, max_time, read_only, args)
        elif (db_type == 'mysql'):
            self.execute_mysql(build, num_threads, max_time, read_only, args)


    def execute_pgsql(self, build, num_threads, max_time, read_only, args):
        bin = os.path.join(self.autodir, 'deps/pgsql/pgsql/bin')
        data = os.path.join(self.autodir, 'deps/pgsql/pgsql/data')
        log = os.path.join(self.debugdir, 'pgsql.log')

        if build == 1:
            utils.system('rm -rf ' + data)
            os.mkdir(data)
            os.chown(data, self.dbuid, 0)
            utils.system(self.sudo + bin + '/initdb -D ' + data)

        # Database must be able to write its output into debugdir
        os.chown(self.debugdir, self.dbuid, 0)
        utils.system(self.sudo + bin + '/pg_ctl -D %s -l %s start' %(data, log))

        # Wait for database to start
        time.sleep(5)

        try:
            base_cmd = self.srcdir + '/sysbench/sysbench --test=oltp ' \
                       '--db-driver=pgsql --pgsql-user=' + self.dbuser

            if build == 1:
                utils.system(self.sudo + bin + '/createdb sbtest')
                cmd = base_cmd +' prepare'
                utils.system(cmd)

            cmd = base_cmd + \
                    ' --num-threads=' + str(num_threads) + \
                    ' --max-time=' + str(max_time) + \
                    ' --max-requests=0'

            if read_only:
                cmd = cmd + ' --oltp-read-only=on'

            self.results.append(utils.system_output(cmd + ' run',
                                                    retain_output=True))

        except:
            utils.system(self.sudo + bin + '/pg_ctl -D ' + data + ' stop')
            raise

        utils.system(self.sudo + bin + '/pg_ctl -D ' + data + ' stop')


    def execute_mysql(self, build, num_threads, max_time, read_only, args):
        bin = os.path.join(self.autodir, 'deps/mysql/mysql/bin')
        data = os.path.join(self.autodir, 'deps/mysql/mysql/var')
        log = os.path.join(self.debugdir, 'mysql.log')

        if build == 1:
            utils.system('rm -rf ' + data)
            os.mkdir(data)
            os.chown(data, self.dbuid, 0)
            utils.system(bin + '/mysql_install_db --user=' + self.dbuser)

        utils.system(bin + '/mysqld_safe --log-error=' + log + \
                ' --user=' + self.dbuser + ' &')

        # Wait for database to start
        time.sleep(5)

        try:
            base_cmd = self.srcdir + '/sysbench/sysbench --test=oltp ' \
                                     '--db-driver=mysql --mysql-user=root'

            if build == 1:
                utils.system('echo "create database sbtest" | ' + \
                        bin + '/mysql -u root')
                cmd = base_cmd +' prepare'
                utils.system(cmd)

            cmd = base_cmd + \
                    ' --num-threads=' + str(num_threads) + \
                    ' --max-time=' + str(max_time) + \
                    ' --max-requests=0'

            if read_only:
                cmd = cmd + ' --oltp-read-only=on'

            self.results.append(utils.system_output(cmd + ' run',
                                                    retain_output=True))

        except:
            utils.system(bin + '/mysqladmin shutdown')
            raise

        utils.system(bin + '/mysqladmin shutdown')


    def postprocess(self):
        self.__format_results("\n".join(self.results))

    def __format_results(self, results):
        threads = 0
        tps = 0

        out = open(self.resultsdir + '/keyval', 'w')
        for line in results.split('\n'):
            threads_re = re.search('Number of threads: (\d+)', line)
            if threads_re:
                threads = threads_re.group(1)

            tps_re = re.search('transactions:\s+\d+\s+\((\S+) per sec.\)', line)
            if tps_re:
                tps = tps_re.group(1)
                break

        out.write('threads=%s\ntps=%s' % (threads, tps))
        out.close()
