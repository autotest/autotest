__author__ = """Copyright Google, Peter Dahl, Martin J. Bligh   2007"""

import os, sys, re, glob, math
from autotest_lib.client.bin import autotest_utils
from autotest_lib.client.common_lib import utils, error

super_root = "/dev/cpuset"


# Convert '1-3,7,9-12' to [1,2,3,7,9,10,11,12]
def rangelist_to_list(rangelist):
    result = []
    if not rangelist:
        return result
    for x in rangelist.split(','):
        if re.match(r'^(\d+)$', x):
            result.append(int(x))
            continue
        m = re.match(r'^(\d+)-(\d+)$', x)
        if m:
            start = int(m.group(1))
            end = int(m.group(2))
            result += range(start, end+1)
            continue
        msg = 'Cannot understand data input: %s %s' % (x, rangelist)
        raise ValueError(msg)
    return result


def rounded_memtotal():
    # Get total of all physical mem, in Kbytes
    usable_Kbytes = autotest_utils.memtotal()
    # usable_Kbytes is system's usable DRAM in Kbytes,
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
    min_Kbytes   = int(usable_Kbytes / (1.0 - mindeduct))
    # increase mem size further by 2**n rounding, by 0..roundKb or more
    round_Kbytes = int(usable_Kbytes / (1.0 - maxdeduct)) - min_Kbytes
    # find least binary roundup 2**n that covers worst-cast roundKb
    mod2n = 1 << int(math.ceil(math.log(round_Kbytes, 2)))
    # have round_Kbytes <= mod2n < round_Kbytes*2
    # round min_Kbytes up to next multiple of mod2n
    phys_Kbytes = min_Kbytes + mod2n - 1
    phys_Kbytes = phys_Kbytes - (phys_Kbytes % mod2n)  # clear low bits
    return phys_Kbytes


def my_container_name():
    # Get current process's inherited or self-built container name
    #   within /dev/cpuset.  Is '/' for root container, '/sys', etc.
    return utils.read_one_line('/proc/%i/cpuset' % os.getpid())


def get_mem_nodes(container_full_name):
    file_name = os.path.join(container_full_name, "mems")
    if os.path.exists(file_name):
        return rangelist_to_list(utils.read_one_line(file_name))
    else:
        return []


def available_exclusive_mem_nodes(parent_container):
    # Get list of numa memory nodes of parent container which could
    #  be allocated exclusively to new child containers.
    # This excludes any nodes now allocated (exclusively or not)
    #  to existing children.
    available = set(get_mem_nodes(parent_container))
    for child_container in glob.glob('%s/*/mems' % parent_container):
        child_container = os.path.dirname(child_container)
        busy = set(get_mem_nodes(child_container))
        available -= busy
    return list(available)


def my_mem_nodes():
    # Get list of numa memory nodes owned by current process's container.
    return get_mem_nodes('/dev/cpuset%s' % my_container_name())


def my_available_exclusive_mem_nodes():
    # Get list of numa memory nodes owned by current process's
    # container, which could be allocated exclusively to new child
    # containers.  This excludes any nodes now allocated
    # (exclusively or not) to existing children.
    return available_exclusive_mem_nodes('/dev/cpuset%s' % my_container_name())


def mbytes_per_mem_node():
    # Get mbyte size of each numa mem node, as float
    # Replaces autotest_utils.node_size().
    # Based on guessed total physical mem size, not on kernel's
    #   lesser 'available memory' after various system tables.
    # Can be non-integer when kernel sets up 15 nodes instead of 16.
    return rounded_memtotal() / (len(autotest_utils.numa_nodes()) * 1024.0)


def get_cpus(container_full_name):
    file_name = os.path.join(container_full_name, "cpus")
    if os.path.exists(file_name):
        return rangelist_to_list(utils.read_one_line(file_name))
    else:
        return []


def my_cpus():
    # Get list of cpu cores owned by current process's container.
    return get_cpus('/dev/cpuset%s' % my_container_name())


def get_tasks(setname):
    return [x.rstrip() for x in open(setname+'/tasks').readlines()]


def print_one_cpuset(name):
    dir = os.path.join('/dev/cpuset', name)
    cpus = utils.read_one_line(dir + '/cpus')
    mems = utils.read_one_line(dir + '/mems')
    node_size_ = int(mbytes_per_mem_node()) << 20
    memtotal = node_size_ * len(rangelist_to_list(mems))
    tasks = ','.join(get_tasks(dir))
    print "cpuset %s: size %s; tasks %s; cpus %s; mems %s" % \
          (name, autotest_utils.human_format(memtotal), tasks, cpus, mems)


def print_all_cpusets():
    for cpuset in glob.glob('/dev/cpuset/*'):
        print_one_cpuset(re.sub(r'.*/', '', cpuset))


def release_dead_containers(parent=super_root):
    # Delete temp subcontainers nested within parent container
    #   that are now dead (having no tasks and no sub-containers)
    #   and recover their cpu and mem resources.
    # Must not call when a parallel task may be allocating containers!
    # Limit to test* names to preserve permanent containers.
    for child in glob.glob('%s/test*' % parent):
        print 'releasing dead container', child
        release_dead_containers(child)  # bottom-up tree walk
        # rmdir has no effect when container still
        #   has tasks or sub-containers
        os.rmdir(child)


def ionice(priority, sched_class=2):
    print "setting disk priority to %d" % priority
    cmd = "/usr/bin/ionice"
    params = "-c%d -n%d -p%d" % (sched_class, priority, os.getpid())
    utils.system(cmd + " " + params)


class cpuset(object):

    def display(self):
        print_one_cpuset(os.path.join(self.root, self.name))


    def release(self):
        print "releasing ", self.cpudir
        parent_t = os.path.join(self.root, 'tasks')
        # Transfer survivors (and self) to parent
        for task in get_tasks(self.cpudir):
            utils.write_one_line(parent_t, task)
        os.rmdir(self.cpudir)
        if os.path.exists(self.cpudir):
            raise error.AutotestError('Could not delete container '
                                      + self.cpudir)


    def setup_network_containers(self, min_tx=0, max_tx=0, priority=2):
        nc_tool = os.path.join(os.path.dirname(__file__), "..", "deps",
                               "network_containers", "network_container")
        cmd = ("%s --class_modify --cpuset_name %s --network_tx_min %d "
               "--network_tx_max %d --network_priority %d")
        cmd %= (nc_tool, self.name, min_tx * 10**6, max_tx * 10**6, priority)
        print "network containers: %s" % cmd
        utils.run(cmd)


    def setup_disk_containers(self, disk):
        self.disk_priorities = disk.get("priorities", range(8))
        default_priority = disk.get("default", max(self.disk_priorities))
        # set the allowed priorities
        path = os.path.join(self.cpudir, "blockio.prios_allowed")
        priorities = ",".join(str(p) for p in self.disk_priorities)
        utils.write_one_line(path, "be:%s" % priorities)
        # set the current process into the default priority
        ionice(default_priority)


    def __init__(self, name, job_size=None, job_pid=None, cpus=None,
                 root=None, network=None, disk=None):
        """\
        Create a cpuset container and move job_pid into it
        Allocate the list "cpus" of cpus to that container

                name = arbitrary string tag
                job_size = reqested memory for job in megabytes
                job_pid = pid of job we're putting into the container
                cpu = list of cpu indicies to associate with the cpuset
                root = the cpuset to create this new set in
                network = a dictionary of params to use for the network
                          container, or None if you do not want to use
                          network containment
                    min_tx = minimum network tx in Mbps
                    max_tx = maximum network tx in Mbps
                    priority = network priority
                disk = a dict of disk prorities to use, or None if you do not
                       want to use disk containment
                    priorities = list of priorities to restrict the cpuset to
                    default = default priority to use, or max(priorities) if
                              not specified
        """
        if not os.path.exists(os.path.join(super_root, "cpus")):
            raise error.AutotestError('Root container /dev/cpuset '
                                      'is empty; please reboot')

        self.name = name

        if root == None:
            # default to nested in process's current container
            root = my_container_name()[1:]
        self.root = os.path.join(super_root, root)
        if not os.path.exists(self.root):
            raise error.AutotestError(('Parent container %s does not exist')
                                       % self.root)

        if job_size == None:
            # default to biggest container we can make under root
            job_size = int( mbytes_per_mem_node() *
                len(available_exclusive_mem_nodes(self.root)) )
        if not job_size:
            raise error.AutotestError('Creating container with no mem')
        self.memory = job_size

        if cpus == None:
            # default to biggest container we can make under root
            cpus = get_cpus(self.root)
        if not cpus:
            raise error.AutotestError('Creating container with no cpus')
        self.cpus = cpus

        # default to the current pid
        if not job_pid:
            job_pid = os.getpid()

        print ("cpuset(name=%s, root=%s, job_size=%d, pid=%d, network=%r, "
               "disk=%r)") % (name, root, job_size, job_pid, network, disk)

        self.cpudir = os.path.join(self.root, name)
        if os.path.exists(self.cpudir):
            self.release()   # destructively replace old

        nodes_needed = int(math.ceil( float(job_size) /
                                math.ceil(mbytes_per_mem_node()) ))

        if nodes_needed > len(get_mem_nodes(self.root)):
            raise error.AutotestError("Container's memory "
                                      "is bigger than parent's")

        while True:
            # Pick specific free mem nodes for this cpuset
            mems = available_exclusive_mem_nodes(self.root)
            if len(mems) < nodes_needed:
                raise error.AutotestError(('Existing container hold %d mem '
                                          'nodes needed by new container')
                                          % (nodes_needed - len(mems)))
            mems = mems[-nodes_needed:]
            mems_spec = ','.join(['%d' % x for x in mems])
            os.mkdir(self.cpudir)
            utils.write_one_line(os.path.join(self.cpudir, 'mem_exclusive'),
                                 '1')
            utils.write_one_line(os.path.join(self.cpudir, 'mems'), mems_spec)
            # Above sends err msg to client.log.0, but no exception,
            #   if mems_spec contained any now-taken nodes
            # Confirm that siblings didn't grab our chosen mems:
            nodes_gotten = len(get_mem_nodes(self.cpudir))
            if nodes_gotten >= nodes_needed:
                break   # success
            print "cpuset %s lost race for nodes" % name, mems_spec
            # Return any mem we did get, and try again
            os.rmdir(self.cpudir)

        # setup up the network container
        if network is not None:
            self.setup_network_containers(**network)
        self.network = network

        # setup up the disk containment
        if disk is not None:
            self.setup_disk_containers(disk)
        else:
            self.disk_priorities = None

        # add specified cpu cores and own task pid to container:
        cpu_spec = ','.join(['%d' % x for x in cpus])
        utils.write_one_line(os.path.join(self.cpudir, 'cpus'), cpu_spec)
        utils.write_one_line(os.path.join(self.cpudir, 'tasks'), "%d" % job_pid)
        self.display()
