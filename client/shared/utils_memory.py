import re, glob, math, logging
from autotest.client import utils


# Returns total memory in kb
def read_from_meminfo(key):
    cmd_result = utils.run('grep %s /proc/meminfo' % key, verbose=False)
    meminfo = cmd_result.stdout
    return int(re.search(r'\d+', meminfo).group(0))


def memtotal():
    return read_from_meminfo('MemTotal')


def freememtotal():
    return read_from_meminfo('MemFree')


def rounded_memtotal():
    # Get total of all physical mem, in kbytes
    usable_kbytes = memtotal()
    # usable_kbytes is system's usable DRAM in kbytes,
    #   as reported by memtotal() from device /proc/meminfo memtotal
    #   after Linux deducts 1.5% to 5.1% for system table overhead
    # Undo the unknown actual deduction by rounding up
    #   to next small multiple of a big power-of-two
    #   eg  12GB - 5.1% gets rounded back up to 12GB
    mindeduct = 0.015  # 1.5 percent
    maxdeduct = 0.055  # 5.5 percent
    # deduction range 1.5% .. 5.5% supports physical mem sizes
    #    6GB .. 12GB in steps of .5GB
    #   12GB .. 24GB in steps of 1 GB
    #   24GB .. 48GB in steps of 2 GB ...
    # Finer granularity in physical mem sizes would require
    #   tighter spread between min and max possible deductions

    # increase mem size by at least min deduction, without rounding
    min_kbytes   = int(usable_kbytes / (1.0 - mindeduct))
    # increase mem size further by 2**n rounding, by 0..roundKb or more
    round_kbytes = int(usable_kbytes / (1.0 - maxdeduct)) - min_kbytes
    # find least binary roundup 2**n that covers worst-cast roundKb
    mod2n = 1 << int(math.ceil(math.log(round_kbytes, 2)))
    # have round_kbytes <= mod2n < round_kbytes*2
    # round min_kbytes up to next multiple of mod2n
    phys_kbytes = min_kbytes + mod2n - 1
    phys_kbytes = phys_kbytes - (phys_kbytes % mod2n)  # clear low bits
    return phys_kbytes


def numa_nodes():
    node_paths = glob.glob('/sys/devices/system/node/node*')
    nodes = [int(re.sub(r'.*node(\d+)', r'\1', x)) for x in node_paths]
    return (sorted(nodes))


def node_size():
    nodes = max(len(numa_nodes()), 1)
    return ((memtotal() * 1024) / nodes)


def get_huge_page_size():
    output = utils.system_output('grep Hugepagesize /proc/meminfo')
    return int(output.split()[1]) # Assumes units always in kB. :(


def get_num_huge_pages():
    raw_hugepages = utils.system_output('/sbin/sysctl vm.nr_hugepages')
    return int(raw_hugepages.split()[2])


def set_num_huge_pages(num):
    utils.system('/sbin/sysctl vm.nr_hugepages=%d' % num)


def drop_caches():
    """Writes back all dirty pages to disk and clears all the caches."""
    utils.run("sync", verbose=False)
    # We ignore failures here as this will fail on 2.6.11 kernels.
    utils.run("echo 3 > /proc/sys/vm/drop_caches", ignore_status=True,
                 verbose=False)
