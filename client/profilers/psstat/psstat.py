"""
Sets up a subprocses to recording process/threads info when system
average load great than 'load_threshold'.

Defaults options:
    interval = 0.5
    top_ps_num = 15
    log_mb_size = 5
    load_threshold = 0.0
    free_mem_before_test = no
    free_mem_after_test = no
"""
import os
import re
import time

from autotest.client import profiler
from autotest.client.shared import utils


def listps(num, order):
    """
    Select top 'num' process order by $order from system.

    :param num: number of process, if 'num' equal '0' list all process
    :param order: order list by a process attribute(eg, pcpu or vsz ...)

    :return: list of process
    """
    cmd = 'ps max -o pid,ppid,pcpu,pmem,rss,vsz,lwp,nlwp,lstart,cmd'
    cmd += ' --sort -%s' % order
    title = 'Process/Threads details:'
    ps_info = utils.system_output(cmd, verbose=False).splitlines()
    if num != 0:
        cnt, idx = 0, 0
        title = 'Top %d process/threads details, ' % num
        title += 'order by %s:' % order
        for line in ps_info:
            idx += 1
            if re.match(r'^\s+\d', line):
                cnt += 1
            if cnt > num:
                break
        ps_info = ps_info[:idx]
    ps_info.insert(0, title)
    return ps_info


def cpuload(cpu_num, prev_total=0, prev_idle=0):
    """
    Calculate average CPU usage.

    :param prev_total: previous total value (default to 0).
    :param prev_idle: previous idle value (default to 0).

    :return: float number of CPU usage.
    """
    cpu_stat = utils.read_one_line('/proc/stat').lstrip('cpu')
    cpu_stat = [int(_) for _ in cpu_stat.split()]
    total, idle = (0, cpu_stat[3])
    for val in cpu_stat:
        total += val
    diff_total = total - prev_total
    diff_idle = idle - prev_idle
    load = float((1000 * (diff_total - diff_idle) / diff_total + 5) / 10)
    load = load / cpu_num
    return (total, idle, load)


def meminfo():
    """
    Get memory information from /proc/meminfo.
    """
    mem_info = ["Memory Info:"]
    mem_info.append(open('/proc/meminfo', 'r').read())
    return mem_info


def swapcached():
    """
    Get Swapcache used.
    """
    mem_info = meminfo()
    for line in mem_info:
        swaped = re.search(r'SwapCached:\s+(\d+)\w+', line)
        if swaped:
            return swaped.group(1)
    return 0


def uptime():
    """
    Get system load average from startup.
    """
    load_avg = ['System Load Average:']
    load_avg += utils.system_output('uptime', verbose=False).splitlines()
    load_avg += ["\n"]
    return load_avg


def vmstat():
    """
    Get memory status information.
    """
    vm_stat = ['vm status:']
    vm_stat += utils.system_output('vmstat', verbose=False).splitlines()
    vm_stat += ["\n"]
    return vm_stat


def iostat():
    """
    Get IO status information.
    """
    io_stat = ['IO status:']
    io_stat += utils.system_output('iostat', verbose=False).splitlines()
    io_stat += ["\n"]
    return io_stat


def freemem():
    """
    Free useless memoery (pagecache, dentries and inodes).
    """
    return utils.run('sync && echo 3 > /proc/sys/vm/drop_caches')


class psstat(profiler.profiler):
    version = 1

    def __get_param(self, key, default):
        if key in self.params:
            try:
                return float(self.params[key])
            except ValueError:
                return self.params[key]
        return default

    def initialize(self, **params):
        self.fd = None
        self.params = params
        self.outfile = 'psstat.log'
        self.interval = self.__get_param('interval', 0.5)

    def start(self, test):
        """
        Monitor system average load each 'interval' seconds and recording
        process/threads info if system loadavg great than 'load_threshold'.
        """
        if self.__get_param('free_mem_before_test', 'no') == 'yes':
            freemem()
        self.child_pid = os.fork()
        if not self.child_pid:
            prev_total, prev_idle = 0, 0
            count, content_size = 0, 0
            ps_num = int(self.__get_param('top_ps_num', 15))
            log_mb_size = int(self.params.get('log_mb_size', 5))
            threshold = float(self.__get_param('load_threshold', 0.0))
            cpu_num = open('/proc/cpuinfo', 'r').read().count('process')
            outfile = os.path.join(test.profdir, self.outfile)
            self.fd = open(outfile, 'a+')
            while True:
                count += 1
                title = '=' * 30 + ' Loop %d ' % count + '=' * 30
                lines = [title]
                swap_cached = swapcached()
                prev_total, prev_idle, cpu_load = cpuload(cpu_num,
                                                          prev_total,
                                                          prev_idle)
                if cpu_load > threshold or swap_cached > 0:
                    lines.extend(uptime())
                    lines.extend(vmstat())
                    lines.extend(meminfo())
                    lines.extend(iostat())
                    # sort process/threads list by pid if list all process,
                    # then list top 'ps_num' process/theads by pmen and pcpu;
                    orders = (ps_num and [['pcpu', 'pmem']] or [['pid']])[0]
                    for _ in orders:
                        lines.extend(listps(ps_num, _))
                    lines = '\n'.join(lines)
                    content_size += len(lines)
                    # Olny keep 5M log
                    if content_size > log_mb_size * 1024 * 1024:
                        self.fd.seek(0)
                        self.fd.truncate()
                        content_size = 0
                    self.fd.write('%s\n' % lines)
                time.sleep(self.interval)

    def stop(self, test):
        """
        Stop monitor subprocses.
        """
        try:
            if self.fd:
                self.fd.flush()
                self.fd.close()
            os.kill(self.child_pid, 15)
        except OSError:
            pass
        if self.__get_param('free_mem_after_test', 'no') == 'yes':
            freemem()

    def report(self, test):
        return None
