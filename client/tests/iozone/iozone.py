import os, re
from autotest.client import test, utils
import postprocessing


class iozone(test.test):
    """
    This autotest module runs the IOzone filesystem benchmark. The benchmark
    generates and measures a variety of file operations. Iozone has been ported
    to many machines and runs under many operating systems.

    Iozone is useful for performing a broad filesystem analysis of a vendor's
    computer platform. The benchmark tests file I/O performance for the
    following operations:

    Read, write, re-read, re-write, read backwards, read strided, fread, fwrite,
    random read, pread ,mmap, aio_read, aio_write

    @author: Ying Tao (yingtao@cn.ibm.com)
    @see: http://www.iozone.org
    """
    version = 5

    def initialize(self):
        self.job.require_gcc()


    def setup(self, tarball='iozone3_408.tar'):
        """
        Builds the given version of IOzone from a tarball.
        @param tarball: Tarball with IOzone
        @see: http://www.iozone.org/src/current/iozone3_408.tar
        """
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(os.path.join(self.srcdir, 'src/current'))
        utils.system('patch -p3 < %s' %
                     os.path.join(self.bindir, 'makefile.patch'))

        arch = utils.get_current_kernel_arch()
        if (arch == 'ppc'):
            utils.make('linux-powerpc')
        elif (arch == 'ppc64'):
            utils.make('linux-powerpc64')
        elif (arch == 'x86_64'):
            utils.make('linux-AMD64')
        else:
            utils.make('linux')


    def run_once(self, dir=None, args=None):
        """
        Runs IOzone with appropriate parameters, record raw results in a per
        iteration raw output file as well as in the results attribute

        @param dir: IOzone file generation dir.
        @param args: Arguments to the iozone program.
        """
        if not dir:
            dir = self.tmpdir
        os.chdir(dir)
        if not args:
            args = '-a'

        cmd = os.path.join(self.srcdir, 'src', 'current', 'iozone')
        self.results = utils.system_output('%s %s' % (cmd, args))
        self.auto_mode = ("-a" in args)

        self.results_path = os.path.join(self.resultsdir,
                                         'raw_output_%s' % self.iteration)
        self.analysisdir = os.path.join(self.resultsdir,
                                        'analysis_%s' % self.iteration)

        utils.open_write_close(self.results_path, self.results)


    def __get_section_name(self, desc):
        return desc.strip().replace(' ', '_')


    def generate_keyval(self):
        keylist = {}

        if self.auto_mode:
            labels = ('write', 'rewrite', 'read', 'reread', 'randread',
                      'randwrite', 'bkwdread', 'recordrewrite',
                      'strideread', 'fwrite', 'frewrite', 'fread', 'freread')
            for line in self.results.splitlines():
                fields = line.split()
                if len(fields) != 15:
                    continue
                try:
                    fields = tuple([int(i) for i in fields])
                except ValueError:
                    continue
                for l, v in zip(labels, fields[2:]):
                    key_name = "%d-%d-%s" % (fields[0], fields[1], l)
                    keylist[key_name] = v
        else:
            child_regexp  = re.compile('Children see throughput for[\s]+'
                            '([\d]+)\s+([-\w]+[-\w\s]*)\=[\s]+([\d\.]*) KB/sec')
            parent_regexp = re.compile('Parent sees throughput for[\s]+'
                            '([\d]+)\s+([-\w]+[-\w\s]*)\=[\s]+([\d\.]*) KB/sec')

            KBsec_regexp  = re.compile('\=[\s]+([\d\.]*) KB/sec')
            KBval_regexp  = re.compile('\=[\s]+([\d\.]*) KB')

            section = None
            w_count = 0

            for line in self.results.splitlines():
                line = line.strip()

                # Check for the beginning of a new result section
                match = child_regexp.search(line)
                if match:
                    # Extract the section name and the worker count
                    w_count = int(match.group(1))
                    section = self.__get_section_name(match.group(2))

                    # Output the appropriate keyval pair
                    key_name = '%s-%d-kids' % (section, w_count)
                    keylist[key_name] = match.group(3)
                    continue

                # Check for any other interesting lines
                if '=' in line:
                    # Is it something we recognize? First check for parent.
                    match = parent_regexp.search(line)
                    if match:
                        # The section name and the worker count better match
                        p_count = int(match.group(1))
                        p_secnt = self.__get_section_name(match.group(2))
                        if p_secnt != section or p_count != w_count:
                            continue

                        # Set the base name for the keyval
                        basekey = 'parent'
                    else:
                        # Check for the various 'throughput' values
                        if line[3:26] == ' throughput per thread ':
                            basekey = line[0:3]
                            match_x = KBsec_regexp
                        else:
                            # The only other thing we expect is 'Min xfer'
                            if not line.startswith('Min xfer '):
                                continue
                            basekey = 'MinXfer'
                            match_x = KBval_regexp

                        match = match_x.search(line)
                        if match:
                            result = match.group(1)
                            key_name = "%s-%d-%s" % (section, w_count, basekey)
                            keylist[key_name] = result

        self.write_perf_keyval(keylist)


    def postprocess_iteration(self):
        self.generate_keyval()
        if self.auto_mode:
            a = postprocessing.IOzoneAnalyzer(list_files=[self.results_path],
                                              output_dir=self.analysisdir)
            a.analyze()
            p = postprocessing.IOzonePlotter(results_file=self.results_path,
                                             output_dir=self.analysisdir)
            p.plot_all()
