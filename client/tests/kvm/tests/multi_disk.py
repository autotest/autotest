"""
multi_disk test for Autotest framework.

@copyright: 2011-2012 Red Hat Inc.
"""
import logging
import re
import random
from autotest.client.shared import error
from autotest.client.virt.virt_env_process import preprocess
from autotest.client.shared import utils
from client.virt import kvm_qtree

_RE_RANGE1 = re.compile(r'range\([ ]*([-]?\d+|n).*\)')
_RE_RANGE2 = re.compile(r',[ ]*([-]?\d+|n)')
_RE_BLANKS = re.compile(r'^([ ]*)')


@error.context_aware
def _range(buf, n=None):
    """
    Converts 'range(..)' string to range. It supports 1-4 args. It supports
    'n' as correct input, which is substituted to return the correct range.
    range1-3 ... ordinary python range()
    range4   ... multiplies the occurrence of each value
                (range(0,4,1,2) => [0,0,1,1,2,2,3,3])
    @raise ValueError: In case incorrect values are given.
    @return: List of int values. In case it can't substitute 'n'
             it returns the original string.
    """
    out = _RE_RANGE1.match(buf)
    if not out:
        return False
    out = [out.groups()[0]]
    out.extend(_RE_RANGE2.findall(buf))
    if 'n' in out:
        if n is None:
            # Don't know what to substitute, return the original
            return buf
        else:
            # Doesn't cover all cases and also it works it's way...
            n = int(n)
            if out[0] == 'n':
                out[0] = int(n)
            if len(out) > 1 and out[1] == 'n':
                out[1] = int(out[0]) + n
            if len(out) > 2 and out[2] == 'n':
                out[2] = (int(out[1]) - int(out[0])) / n
            if len(out) > 3 and out[3] == 'n':
                _len = len(range(int(out[0]), int(out[1]), int(out[2])))
                out[3] = n / _len
                if n % _len:
                    out[3] += 1
    for i in range(len(out)):
        out[i] = int(out[i])
    if len(out) == 1:
        out = range(out[0])
    elif len(out) == 2:
        out = range(out[0], out[1])
    elif len(out) == 3:
        out = range(out[0], out[1], out[2])
    elif len(out) == 4:
        # arg4 * range
        _out = []
        for _ in range(out[0], out[1], out[2]):
            _out.extend([_] * out[3])
        out = _out
    else:
        raise ValueError("More than 4 parameters in _range()")
    return out


@error.context_aware
def run_multi_disk(test, params, env):
    """
    Test multi disk suport of guest, this case will:
    1) Create disks image in configuration file.
    2) Start the guest with those disks.
    3) Checks qtree vs. test params.
    4) Format those disks.
    5) Copy file into / out of those disks.
    6) Compare the original file and the copied file using md5 or fc comand.
    7) Repeat steps 3-5 if needed.

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    def _add_param(name, value):
        """ Converts name+value to stg_params string """
        if value:
            value = re.sub(' ', '\\ ', value)
            return " %s:%s " % (name, value)
        else:
            return ''

    stg_image_num = 0
    stg_params = params.get("stg_params", "")
    # Compatibility
    stg_params += _add_param("image_size", params.get("stg_image_size"))
    stg_params += _add_param("image_format", params.get("stg_image_format"))
    stg_params += _add_param("image_boot", params.get("stg_image_boot"))
    stg_params += _add_param("drive_format", params.get("stg_drive_format"))
    if params.get("stg_assign_index") != "no":
        # Assume 0 and 1 are already occupied (hd0 and cdrom)
        stg_params += _add_param("drive_index", 'range(2,n)')
    param_matrix = {}

    stg_params = stg_params.split(' ')
    i = 0
    while i < len(stg_params) - 1:
        if not stg_params[i].strip():
            i += 1
            continue
        if stg_params[i][-1] == '\\':
            stg_params[i] = '%s %s' % (stg_params[i][:-1],
                                          stg_params.pop(i + 1))
        i += 1

    rerange = []
    has_name = False
    for i in xrange(len(stg_params)):
        if not stg_params[i].strip():
            continue
        (cmd, parm) = stg_params[i].split(':', 1)
        if cmd == "image_name":
            has_name = True
        if _RE_RANGE1.match(parm):
            parm = _range(parm)
            if parm == False:
                raise error.TestError("Incorrect cfg: stg_params %s looks "
                                      "like range(..) but doesn't contain "
                                      "numbers." % cmd)
            param_matrix[cmd] = parm
            if type(parm) is str:
                # When we know the stg_image_num, substitute it.
                rerange.append(cmd)
                continue
        else:
            # ',' separated list of values
            parm = parm.split(',')
            j = 0
            while j < len(parm) - 1:
                if parm[j][-1] == '\\':
                    parm[j] = '%s,%s' % (parm[j][:-1], parm.pop(j + 1))
                j += 1
            param_matrix[cmd] = parm
        stg_image_num = max(stg_image_num, len(parm))

    stg_image_num = int(params.get('stg_image_num', stg_image_num))
    for cmd in rerange:
        param_matrix[cmd] = _range(param_matrix[cmd], stg_image_num)
    # param_table* are for pretty print of param_matrix
    param_table = []
    param_table_header = ['name']
    if not has_name:
        param_table_header.append('image_name')
    for _ in param_matrix:
        param_table_header.append(_)

    stg_image_name = params.get('stg_image_name', '%s')
    for i in xrange(stg_image_num):
        name = "stg%d" % i
        params['images'] += " %s" % name
        param_table.append([])
        param_table[-1].append(name)
        if not has_name:
            params["image_name_%s" % name] = stg_image_name % name
            param_table[-1].append(params.get("image_name_%s" % name))
        for parm in param_matrix.iteritems():
            params['%s_%s' % (parm[0], name)] = str(parm[1][i % len(parm[1])])
            param_table[-1].append(params.get('%s_%s' % (parm[0], name)))

    if params.get("multi_disk_params_only") == 'yes':
        # Only print the test param_matrix and finish
        logging.info('Newly added disks:\n%s',
                     utils.matrix_to_string(param_table, param_table_header))
        return

    # Always recreate VM (disks are already marked for deletion
    preprocess(test, params, env)
    vm = env.get_vm(params["main_vm"])
    vm.create(timeout=max(10, stg_image_num))
    session = vm.wait_for_login(timeout=int(params.get("login_timeout", 360)))

    images = params.get("images").split()
    n_repeat = int(params.get("n_repeat", "1"))
    image_num = len(images)
    file_system = params.get("file_system").split()
    fs_num = len(file_system)
    cmd_timeout = float(params.get("cmd_timeout", 360))
    re_str = params.get("re_str")
    block_list = params.get("block_list").split()

    error.context("verifying qtree vs. test params")
    err = 0
    qtree = kvm_qtree.QtreeContainer()
    qtree.parse_info_qtree(vm.monitor.info('qtree'))
    disks = kvm_qtree.QtreeDisksContainer(qtree.get_nodes())
    (tmp1, tmp2) = disks.parse_info_block(vm.monitor.info('block'))
    err += tmp1 + tmp2
    err += disks.generate_params()
    err += disks.check_disk_params(params, vm.root_dir)
    (tmp1, tmp2, _, _) = disks.check_guests_proc_scsi(
                                    session.cmd_output('cat /proc/scsi/scsi'))
    err += tmp1 + tmp2

    if err:
        raise error.TestFail("%s errors occurred while verifying qtree vs. "
                             "params" % err)
    if params.get('multi_disk_only_qtree') == 'yes':
        return

    try:
        if params.get("clean_cmd"):
            cmd = params.get("clean_cmd")
            session.cmd_status_output(cmd)
        if params.get("pre_cmd"):
            cmd = params.get("pre_cmd")
            error.context("creating partition on test disk")
            session.cmd(cmd, timeout=cmd_timeout)
        cmd = params.get("list_volume_command")
        output = session.cmd_output(cmd, timeout=cmd_timeout)
        disks = re.findall(re_str, output)
        disks.sort()
        logging.debug("Volume list that meets regular expressions: %s", disks)
        if len(disks) < image_num:
            raise error.TestFail("Fail to list all the volumes!")

        tmp_list = []
        for disk in disks:
            if disk.strip() in block_list:
                tmp_list.append(disk)
        for disk in tmp_list:
            logging.info("No need to check volume %s", disk)
            disks.remove(disk)

        for i in range(n_repeat):
            logging.info("iterations: %s", (i + 1))
            for disk in disks:
                disk = disk.strip()

                logging.info("Format disk: %s...", disk)
                index = random.randint(0, fs_num - 1)

                # Random select one file system from file_system
                fs = file_system[index].strip()
                cmd = params.get("format_command") % (fs, disk)
                error.context("formatting test disk")
                session.cmd(cmd, timeout=cmd_timeout)
                if params.get("mount_command"):
                    cmd = params.get("mount_command") % (disk, disk, disk)
                    session.cmd(cmd, timeout=cmd_timeout)

            for disk in disks:
                disk = disk.strip()

                logging.info("Performing I/O on disk: %s...", disk)
                cmd_list = params.get("cmd_list").split()
                for cmd_l in cmd_list:
                    if params.get(cmd_l):
                        cmd = params.get(cmd_l) % disk
                        session.cmd(cmd, timeout=cmd_timeout)

                cmd = params.get("compare_command")
                output = session.cmd_output(cmd)
                key_word = params.get("check_result_key_word")
                if key_word and key_word in output:
                    logging.debug("Guest's virtual disk %s works fine", disk)
                elif key_word:
                    raise error.TestFail("Files on guest os root fs and disk "
                                         "differ")
                else:
                    raise error.TestError("Param check_result_key_word was not "
                                          "specified! Please check your config")

            if params.get("umount_command"):
                cmd = params.get("show_mount_cmd")
                output = session.cmd_output(cmd)
                disks = re.findall(re_str, output)
                disks.sort()
                for disk in disks:
                    disk = disk.strip()
                    cmd = params.get("umount_command") % (disk, disk)
                    error.context("unmounting test disk")
                    session.cmd(cmd)
    finally:
        if params.get("post_cmd"):
            cmd = params.get("post_cmd")
            session.cmd(cmd)
        session.close()
