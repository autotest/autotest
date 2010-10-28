# Copyright 2007-2010 Google Inc.  Released under the GPL v2
__author__ = "duanes (Duane Sand), pdahl (Peter Dahl)"

# A basic cpuset/cgroup container manager for limiting memory use during tests
#   for use on kernels not running some site-specific container manager

import os, sys, re, glob, fcntl, logging
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

SUPER_ROOT = ''      # root of all containers or cgroups
NO_LIMIT = (1 << 63) - 1   # containername/memory.limit_in_bytes if no limit

# propio service classes:
PROPIO_PRIO = 1
PROPIO_NORMAL = 2
PROPIO_IDLE = 3

super_root_path = ''    # usually '/dev/cgroup'; '/dev/cpuset' on 2.6.18
cpuset_prefix   = None  # usually 'cpuset.'; '' on 2.6.18
fake_numa_containers = False # container mem via numa=fake mem nodes, else pages
mem_isolation_on = False
node_mbytes = 0         # mbytes in one typical mem node
root_container_bytes = 0  # squishy limit on effective size of root container


def discover_container_style():
    global super_root_path, cpuset_prefix
    global mem_isolation_on, fake_numa_containers
    global node_mbytes, root_container_bytes
    if super_root_path != '':
        return  # already looked up
    if os.path.exists('/dev/cgroup/tasks'):
        # running on 2.6.26 or later kernel with containers on:
        super_root_path = '/dev/cgroup'
        cpuset_prefix = 'cpuset.'
        if get_boot_numa():
            mem_isolation_on = fake_numa_containers = True
        else:  # memcg containers IFF compiled-in & mounted & non-fakenuma boot
            fake_numa_containers = False
            mem_isolation_on = os.path.exists(
                    '/dev/cgroup/memory.limit_in_bytes')
            # TODO: handle possibility of where memcg is mounted as its own
            #       cgroup hierarchy, separate from cpuset??
    elif os.path.exists('/dev/cpuset/tasks'):
        # running on 2.6.18 kernel with containers on:
        super_root_path = '/dev/cpuset'
        cpuset_prefix = ''
        mem_isolation_on = fake_numa_containers = get_boot_numa() != ''
    else:
        # neither cpuset nor cgroup filesystem active:
        super_root_path = None
        cpuset_prefix = 'no_cpusets_or_cgroups_exist'
        mem_isolation_on = fake_numa_containers = False

    logging.debug('mem_isolation: %s', mem_isolation_on)
    logging.debug('fake_numa_containers: %s', fake_numa_containers)
    if fake_numa_containers:
        node_mbytes = int(mbytes_per_mem_node())
    elif mem_isolation_on:  # memcg-style containers
        # For now, limit total of all containers to using just 98% of system's
        #   visible total ram, to avoid oom events at system level, and avoid
        #   page reclaim overhead from going above kswapd highwater mark.
        system_visible_pages = utils.memtotal() >> 2
        usable_pages = int(system_visible_pages * 0.98)
        root_container_bytes = usable_pages << 12
        logging.debug('root_container_bytes: %s',
                      utils.human_format(root_container_bytes))


def need_mem_containers():
    discover_container_style()
    if not mem_isolation_on:
        raise error.AutotestError('Mem-isolation containers not enabled '
                                  'by latest reboot')

def need_fake_numa():
    discover_container_style()
    if not fake_numa_containers:
        raise error.AutotestError('fake=numa not enabled by latest reboot')


def full_path(container_name):
    discover_container_style()
    return os.path.join(super_root_path, container_name)


def unpath(container_path):
    return container_path[len(super_root_path)+1:]


def cpuset_attr(container_name, attr):
    discover_container_style()
    return os.path.join(super_root_path, container_name, cpuset_prefix+attr)


def io_attr(container_name, attr):
    discover_container_style()
    # current version assumes shared cgroup hierarchy
    return os.path.join(super_root_path, container_name, 'io.'+attr)


def tasks_path(container_name):
    return os.path.join(full_path(container_name), 'tasks')


def mems_path(container_name):
    return cpuset_attr(container_name, 'mems')


def memory_path(container_name):
    return os.path.join(super_root_path, container_name, 'memory')


def cpus_path(container_name):
    return cpuset_attr(container_name, 'cpus')


def container_exists(name):
    return name is not None and os.path.exists(tasks_path(name))


def move_tasks_into_container(name, tasks):
    task_file = tasks_path(name)
    for task in tasks:
        try:
            logging.debug('moving task %s into container "%s"', task, name)
            utils.write_one_line(task_file, task)
        except Exception:
            if utils.pid_is_alive(task):
                raise   # task exists but couldn't move it
            # task is gone or zombie so ignore this exception


def move_self_into_container(name):
    me = str(os.getpid())
    move_tasks_into_container(name, [me])
    logging.debug('running self (pid %s) in container "%s"', me, name)


def _avail_mbytes_via_nodes(parent):
    # total mbytes of mem nodes available for new containers in parent
    free_nodes = available_exclusive_mem_nodes(parent)
    mbytes = nodes_avail_mbytes(free_nodes)
    # don't have exact model for how container mgr measures mem space
    # better here to underestimate than overestimate
    mbytes = max(mbytes - node_mbytes//2, 0)
    return mbytes


def _avail_bytes_via_pages(parent):
    # Get memory bytes available to parent container which could
    #  be allocated exclusively to new child containers.
    # This excludes mem previously allocated to existing children.
    available = container_bytes(parent)
    mem_files_pattern = os.path.join(full_path(parent),
                                     '*', 'memory.limit_in_bytes')
    for mem_file in glob.glob(mem_files_pattern):
        child_container = unpath(os.path.dirname(mem_file))
        available -= container_bytes(child_container)
    return available


def avail_mbytes(parent=SUPER_ROOT):
    # total mbytes available in parent, for exclusive use in new containers
    if fake_numa_containers:
        return _avail_mbytes_via_nodes(parent)
    else:
        return _avail_bytes_via_pages(parent) >> 20


def delete_leftover_test_containers():
    # recover mems and cores tied up by containers of prior failed tests:
    for child in inner_containers_of(SUPER_ROOT):
        _release_container_nest(child)


def my_lock(lockname):
    # lockname is 'inner'
    lockdir = os.environ['AUTODIR']
    lockname = os.path.join(lockdir, '.cpuset.lock.'+lockname)
    lockfile = open(lockname, 'w')
    fcntl.flock(lockfile, fcntl.LOCK_EX)
    return lockfile


def my_unlock(lockfile):
    fcntl.flock(lockfile, fcntl.LOCK_UN)
    lockfile.close()


# Convert '1-3,7,9-12' to set(1,2,3,7,9,10,11,12)
def rangelist_to_set(rangelist):
    result = set()
    if not rangelist:
        return result
    for x in rangelist.split(','):
        if re.match(r'^(\d+)$', x):
            result.add(int(x))
            continue
        m = re.match(r'^(\d+)-(\d+)$', x)
        if m:
            start = int(m.group(1))
            end = int(m.group(2))
            result.update(set(range(start, end+1)))
            continue
        msg = 'Cannot understand data input: %s %s' % (x, rangelist)
        raise ValueError(msg)
    return result


def my_container_name():
    # Get current process's inherited or self-built container name
    #   within /dev/cpuset or /dev/cgroup.  Is '' for root container.
    name = utils.read_one_line('/proc/%i/cpuset' % os.getpid())
    return name[1:]   # strip leading /


def get_mem_nodes(container_name):
    # all mem nodes now available to a container, both exclusive & shared
    file_name = mems_path(container_name)
    if os.path.exists(file_name):
        return rangelist_to_set(utils.read_one_line(file_name))
    else:
        return set()


def _busy_mem_nodes(parent_container):
    # Get set of numa memory nodes now used (exclusively or shared)
    #   by existing children of parent container
    busy = set()
    mem_files_pattern = os.path.join(full_path(parent_container),
                                     '*', cpuset_prefix+'mems')
    for mem_file in glob.glob(mem_files_pattern):
        child_container = os.path.dirname(mem_file)
        busy |= get_mem_nodes(child_container)
    return busy


def available_exclusive_mem_nodes(parent_container):
    # Get subset of numa memory nodes of parent container which could
    #  be allocated exclusively to new child containers.
    # This excludes nodes now allocated to existing children.
    need_fake_numa()
    available = get_mem_nodes(parent_container)
    available -= _busy_mem_nodes(parent_container)
    return available


def my_mem_nodes():
    # Get set of numa memory nodes owned by current process's container.
    discover_container_style()
    if not mem_isolation_on:
        return set()    # as expected by vmstress
    return get_mem_nodes(my_container_name())


def my_available_exclusive_mem_nodes():
    # Get subset of numa memory nodes owned by current process's
    # container, which could be allocated exclusively to new child
    # containers.  This excludes any nodes now allocated
    # to existing children.
    return available_exclusive_mem_nodes(my_container_name())


def node_avail_kbytes(node):
    return node_mbytes << 10  # crude; fixed numa node size


def nodes_avail_mbytes(nodes):
    # nodes' combined user+avail size, in Mbytes
    return sum(node_avail_kbytes(n) for n in nodes) // 1024


def container_bytes(name):
    if fake_numa_containers:
        return nodes_avail_mbytes(get_mem_nodes(name)) << 20
    else:
        while True:
            file = memory_path(name) + '.limit_in_bytes'
            limit = int(utils.read_one_line(file))
            if limit < NO_LIMIT:
                return limit
            if name == SUPER_ROOT:
                return root_container_bytes
            name = os.path.dirname(name)


def container_mbytes(name):
    return container_bytes(name) >> 20


def mbytes_per_mem_node():
    # Get mbyte size of standard numa mem node, as float
    #  (some nodes are bigger than this)
    # Replaces utils.node_size().
    numa = get_boot_numa()
    if numa.endswith('M'):
        return float(numa[:-1])  # mbyte size of fake nodes
    elif numa:
        nodecnt = int(numa)  # fake numa mem nodes for container isolation
    else:
        nodecnt = len(utils.numa_nodes())  # phys mem-controller nodes
    # Use guessed total physical mem size, not kernel's
    #   lesser 'available memory' after various system tables.
    return utils.rounded_memtotal() / (nodecnt * 1024.0)


def get_cpus(container_name):
    file_name = cpus_path(container_name)
    if os.path.exists(file_name):
        return rangelist_to_set(utils.read_one_line(file_name))
    else:
        return set()


def get_tasks(container_name):
    file_name = tasks_path(container_name)
    try:
        tasks = [x.rstrip() for x in open(file_name).readlines()]
    except IOError:
        if os.path.exists(file_name):
            raise
        tasks = []   # container doesn't exist anymore
    return tasks


def inner_containers_of(parent):
    pattern = os.path.join(full_path(parent), '*/tasks')
    return [unpath(os.path.dirname(task_file))
            for task_file in glob.glob(pattern)]


def _release_container_nest(nest):
    # Destroy a container, and any nested sub-containers
    nest_path = full_path(nest)
    if os.path.exists(nest_path):

        # bottom-up walk of tree, releasing all nested sub-containers
        for child in inner_containers_of(nest):
            _release_container_nest(child)

        logging.debug("releasing container %s", nest)

        # Transfer any survivor tasks (e.g. self) to parent container
        parent = os.path.dirname(nest)
        move_tasks_into_container(parent, get_tasks(nest))

        # remove the now-empty outermost container of this nest
        if os.path.exists(nest_path):
            os.rmdir(nest_path)  # nested, or dead manager


def release_container(container_name=None):
    # Destroy a container
    my_container = my_container_name()
    if container_name is None:
        container_name = my_container
    _release_container_nest(container_name)
    displaced = my_container_name()
    if displaced != my_container:
        logging.debug('now running self (pid %d) in container "%s"',
                      os.getpid(), displaced)


def remove_empty_prio_classes(prios):
    # remove prio classes whose set of allowed priorities is empty
    #    e.g  'no:3;rt:;be:3;id:'  -->  'no:3;be:3'
    return ';'.join(p for p in prios.split(';') if p.split(':')[1])


def all_drive_names():
    # list of all disk drives sda,sdb,...
    paths = glob.glob('/sys/block/sd*')
    if not paths:
        paths = glob.glob('/sys/block/hd*')
    return [os.path.basename(path) for path in paths]


def set_io_controls(container_name, disks=[], ioprio_classes=[PROPIO_NORMAL],
                    io_shares=[95], io_limits=[0]):
    # set the propio controls for one container, for selected disks
    # writing directly to /dev/cgroup/container_name/io.io_service_level
    #    without using containerd or container.py
    # See wiki ProportionalIOScheduler for definitions
    # ioprio_classes: list of service classes, one per disk
    #    using numeric propio service classes as used by kernel API, namely
    #       1: RT, Real Time, aka PROPIO_PRIO
    #       2: BE, Best Effort, aka PROPIO_NORMAL
    #       3: PROPIO_IDLE
    # io_shares: list of disk-time-fractions, one per disk,
    #       as percentage integer 0..100
    # io_limits: list of limit on/off, one per disk
    #       0: no limit, shares use of other containers' unused disk time
    #       1: limited, container's use of disk time is capped to given DTF
    # ioprio_classes defaults to best-effort
    # io_limit defaults to no limit, use slack time
    if not disks:  # defaults to all drives
        disks = all_drive_names()
        io_shares      = [io_shares     [0]] * len(disks)
        ioprio_classes = [ioprio_classes[0]] * len(disks)
        io_limits      = [io_limits     [0]] * len(disks)
    if not (len(disks) == len(ioprio_classes) and len(disks) == len(io_shares)
                                              and len(disks) == len(io_limits)):
        raise error.AutotestError('Unequal number of values for io controls')
    service_level = io_attr(container_name, 'io_service_level')
    if not os.path.exists(service_level):
        return  # kernel predates propio features
            # or io cgroup is mounted separately from cpusets
    disk_infos = []
    for disk,ioclass,limit,share in zip(disks, ioprio_classes,
                                        io_limits, io_shares):
        parts = (disk, str(ioclass), str(limit), str(share))
        disk_info = ' '.join(parts)
        utils.write_one_line(service_level, disk_info)
        disk_infos.append(disk_info)
    logging.debug('set_io_controls of %s to %s',
                  container_name, ', '.join(disk_infos))


def abbrev_list(vals):
    """Condense unsigned (0,4,5,6,7,10) to '0,4-7,10'."""
    ranges = []
    lower = 0
    upper = -2
    for val in sorted(vals)+[-1]:
        if val != upper+1:
            if lower == upper:
                ranges.append(str(lower))
            elif lower <= upper:
                ranges.append('%d-%d' % (lower, upper))
            lower = val
        upper = val
    return ','.join(ranges)


def create_container_with_specific_mems_cpus(name, mems, cpus):
    need_fake_numa()
    os.mkdir(full_path(name))
    utils.write_one_line(cpuset_attr(name, 'mem_hardwall'), '1')
    utils.write_one_line(mems_path(name), ','.join(map(str, mems)))
    utils.write_one_line(cpus_path(name), ','.join(map(str, cpus)))
    logging.debug('container %s has %d cpus and %d nodes totalling %s bytes',
                  name, len(cpus), len(get_mem_nodes(name)),
                  utils.human_format(container_bytes(name)) )


def create_container_via_memcg(name, parent, bytes, cpus):
    # create container via direct memcg cgroup writes
    os.mkdir(full_path(name))
    nodes = utils.read_one_line(mems_path(parent))
    utils.write_one_line(mems_path(name), nodes)  # inherit parent's nodes
    utils.write_one_line(memory_path(name)+'.limit_in_bytes', str(bytes))
    utils.write_one_line(cpus_path(name), ','.join(map(str, cpus)))
    logging.debug('Created container %s directly via memcg,'
                  ' has %d cpus and %s bytes',
                  name, len(cpus), utils.human_format(container_bytes(name)))


def _create_fake_numa_container_directly(name, parent, mbytes, cpus):
    need_fake_numa()
    lockfile = my_lock('inner')   # serialize race between parallel tests
    try:
        # Pick specific mem nodes for new cpuset's exclusive use
        # For now, arbitrarily pick highest available node numbers
        needed_kbytes = mbytes * 1024
        nodes = sorted(list(available_exclusive_mem_nodes(parent)))
        kbytes = 0
        nodecnt = 0
        while kbytes < needed_kbytes and nodecnt < len(nodes):
            nodecnt += 1
            kbytes += node_avail_kbytes(nodes[-nodecnt])
        if kbytes < needed_kbytes:
            parent_mbytes = container_mbytes(parent)
            if mbytes > parent_mbytes:
                raise error.AutotestError(
                      "New container's %d Mbytes exceeds "
                      "parent container's %d Mbyte size"
                      % (mbytes, parent_mbytes) )
            else:
                raise error.AutotestError(
                      "Existing sibling containers hold "
                      "%d Mbytes needed by new container"
                      % ((needed_kbytes - kbytes)//1024) )
        mems = nodes[-nodecnt:]

        create_container_with_specific_mems_cpus(name, mems, cpus)
    finally:
        my_unlock(lockfile)


def create_container_directly(name, mbytes, cpus):
    parent = os.path.dirname(name)
    if fake_numa_containers:
        _create_fake_numa_container_directly(name, parent, mbytes, cpus)
    else:
        create_container_via_memcg(name, parent, mbytes<<20, cpus)


def create_container_with_mbytes_and_specific_cpus(name, mbytes,
                cpus=None, root=SUPER_ROOT, io={}, move_in=True, timeout=0):
    """\
    Create a cpuset container and move job's current pid into it
    Allocate the list "cpus" of cpus to that container

            name = arbitrary string tag
            mbytes = reqested memory for job in megabytes
            cpus = list of cpu indicies to associate with the cpuset
                  defaults to all cpus avail with given root
            root = the parent cpuset to nest this new set within
                   '': unnested top-level container
            io = arguments for proportional IO containers
            move_in = True: Move current process into the new container now.
            timeout = must be 0: persist until explicitly deleted.
    """
    need_mem_containers()
    if not container_exists(root):
        raise error.AutotestError('Parent container "%s" does not exist'
                                   % root)
    if cpus is None:
        # default to biggest container we can make under root
        cpus = get_cpus(root)
    else:
        cpus = set(cpus)  # interface uses list
    if not cpus:
        raise error.AutotestError('Creating container with no cpus')
    name = os.path.join(root, name)  # path relative to super_root
    if os.path.exists(full_path(name)):
        raise error.AutotestError('Container %s already exists' % name)
    create_container_directly(name, mbytes, cpus)
    set_io_controls(name, **io)
    if move_in:
        move_self_into_container(name)
    return name


def get_boot_numa():
    # get boot-time numa=fake=xyz option for current boot
    #   eg  numa=fake=nnn,  numa=fake=nnnM, or nothing
    label = 'numa=fake='
    for arg in utils.read_one_line('/proc/cmdline').split():
        if arg.startswith(label):
            return arg[len(label):]
    return ''
