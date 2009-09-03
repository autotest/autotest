import os, re
from autotest_lib.client.bin import test, os_dep, utils


def convert_size(values):
    values = values.split(':')
    size = values[0]
    if len(values) > 1:
        chunk = values[1]
    else:
        chunk = 0
    if size.endswith('G') or size.endswith('g'):
        size = int(size[:-1]) * 2**30
    else:
        if size.endswith('M') or size.endswith('m'):
            size = int(size[:-1])
        size = int(size) * 2**20
    if chunk:
        if chunk.endswith('K') or chunk.endswith('k'):
            chunk = int(chunk[:-1]) * 2**10
        else:
            chunk = int(chunk)
    return [size, chunk]


class bonnie(test.test):
    version = 1

    def initialize(self):
        self.job.require_gcc()
        self.results = []

    # http://www.coker.com.au/bonnie++/bonnie++-1.03a.tgz
    def setup(self, tarball = 'bonnie++-1.03a.tgz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        os_dep.command('g++')
        utils.system('patch -p1 < ../bonnie++-1.03a-gcc43.patch')
        utils.system('./configure')
        utils.system('make')


    def run_once(self, dir=None, extra_args='', user='root'):
        if not dir:
            dir = self.tmpdir

        # if the user specified a -n we will use that
        if '-n' not in extra_args:
            extra_args += ' -n 2048'
        args = '-d ' + dir + ' -u ' + user + ' ' + extra_args
        cmd = self.srcdir + '/bonnie++ ' + args

        self.results.append(utils.system_output(cmd, retain_output=True))


    def postprocess(self):
        strip_plus = lambda s: re.sub(r"^\++$", "0", s)

        keys = ('size', 'chnk', 'seqout_perchr_ksec',
                'seqout_perchr_pctcp', 'seqout_perblk_ksec',
                'seqout_perblk_pctcp', 'seqout_rewrite_ksec',
                'seqout_rewrite_pctcp', 'seqin_perchr_ksec',
                'seqin_perchr_pctcp', 'seqin_perblk_ksec',
                'seqin_perblk_pctcp', 'rand_ksec', 'rand_pctcp', 'files',
                'seqcreate_create_ksec', 'seqcreate_create_pctcp',
                'seqcreate_read_ksec', 'seqcreate_read_pctcp',
                'seqcreate_delete_ksec', 'seqcreate_delete_pctcp',
                'randreate_create_ksec', 'randcreate_create_pctcp',
                'randcreate_read_ksec', 'randcreate_read_pctcp',
                'randcreate_delete_ksec', 'randcreate_delete_pctcp')

        for line in self.results:
            if line.count(',') != 26:
                continue
            fields = line.split(',')
            fields = [strip_plus(f) for f in fields]
            fields = convert_size(fields[1]) + fields[2:]

            self.write_perf_keyval(dict(zip(keys,fields)))
