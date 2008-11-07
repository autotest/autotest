"""This module gives the mkfs creation options for an existing filesystem.

tune2fs or xfs_growfs is called according to the filesystem. The results,
filesystem tunables, are parsed and mapped to corresponding mkfs options.
"""
import os, re, tempfile
import common
from autotest_lib.client.common_lib import error, utils


def opt_string2dict(opt_string):
    """Breaks the mkfs.ext* option string into dictionary."""
    # Example string: '-j -q -i 8192 -b 4096'. There may be extra whitespaces.
    opt_dict = {}

    for item in opt_string.split('-'):
        item = item.strip()
        if ' ' in item:
            (opt, value) = item.split(' ', 1)
            opt_dict['-%s' % opt] = value
        elif item != '':
            opt_dict['-%s' % item] = None
    # Convert all the digit strings to int.
    for key, value in opt_dict.iteritems():
        if value and value.isdigit():
            opt_dict[key] = int(value)

    return opt_dict


def parse_mke2fs_conf(fs_type, conf_file='/etc/mke2fs.conf'):
    """Parses mke2fs config file for default settings."""
    # Please see /ect/mke2fs.conf for an example.
    default_opt = {}
    fs_opt = {}
    current_fs_type = ''
    current_section = ''
    f = open(conf_file, 'r')
    for line in f:
        if '[defaults]' == line.strip():
            current_section = '[defaults]'
        elif '[fs_types]' == line.strip():
            current_section = '[fs_types]'
        elif current_section == '[defaults]':
            components = line.split('=', 1)
            if len(components) == 2:
                default_opt[components[0].strip()] = components[1].strip()
        elif current_section == '[fs_types]':
            m = re.search('(\w+) = {', line)
            if m:
                current_fs_type = m.group(1)
            else:
                components = line.split('=', 1)
                if len(components) == 2 and current_fs_type == fs_type:
                    default_opt[components[0].strip()] = components[1].strip()
    f.close()

    # fs_types options override the defaults options
    for key, value in fs_opt.iteritems():
        default_opt[key] = value

    # Convert all the digit strings to int.
    for key, value in default_opt.iteritems():
        if value and value.isdigit():
            default_opt[key] = int(value)

    return default_opt


def convert_conf_opt(default_opt):
    conf_opt_mapping = {'blocksize': '-b',
                        'inode_ratio': '-i',
                        'inode_size': '-I'}
    mkfs_opt = {}

    # Here we simply concatenate the feature string while we really need
    # to do the better and/or operations.
    if 'base_features' in default_opt:
        mkfs_opt['-O'] = default_opt['base_features']
    if 'default_features' in default_opt:
        mkfs_opt['-O'] += ',%s' % default_opt['default_features']
    if 'features' in default_opt:
        mkfs_opt['-O'] += ',%s' % default_opt['features']

    for key, value in conf_opt_mapping.iteritems():
        if key in default_opt:
            mkfs_opt[value] = default_opt[key]

    if '-O' in mkfs_opt:
        mkfs_opt['-O'] = mkfs_opt['-O'].split(',')

    return mkfs_opt


def merge_ext_features(conf_feature, user_feature):
    user_feature_list = user_feature.split(',')

    merged_feature = []
    # Removes duplicate entries in conf_list.
    for item in conf_feature:
        if item not in merged_feature:
            merged_feature.append(item)

    # User options override config options.
    for item in user_feature_list:
        if item[0] == '^':
            if item[1:] in merged_feature:
                merged_feature.remove(item[1:])
            else:
                merged_feature.append(item)
        elif item not in merged_feature:
            merged_feature.append(item)
    return merged_feature


def ext_tunables(dev):
    """Call tune2fs -l and parse the result."""
    cmd = 'tune2fs -l %s' % dev
    try:
        out = utils.system_output(cmd)
    except error.CmdError:
        tools_dir = os.path.join(os.environ['AUTODIR'], 'tools')
        cmd = '%s/tune2fs.ext4dev -l %s' % (tools_dir, dev)
        out = utils.system_output(cmd)
    # Load option mappings
    tune2fs_dict = {}
    for line in out.splitlines():
        components = line.split(':', 1)
        if len(components) == 2:
            value = components[1].strip()
            option = components[0]
            if value.isdigit():
                tune2fs_dict[option] = int(value)
            else:
                tune2fs_dict[option] = value

    return tune2fs_dict


def ext_mkfs_options(tune2fs_dict, mkfs_option):
    """Map the tune2fs options to mkfs options."""

    def __inode_count(tune_dict, k):
        return (tune_dict['Block count']/tune_dict[k] + 1) * (
            tune_dict['Block size'])

    def __block_count(tune_dict, k):
        return int(100*tune_dict[k]/tune_dict['Block count'] + 1)

    def __volume_name(tune_dict, k):
        if tune_dict[k] != '<none>':
            return tune_dict[k]
        else:
            return ''

    # mappings between fs features and mkfs options
    ext_mapping = {'Blocks per group': '-g',
                   'Block size': '-b',
                   'Filesystem features': '-O',
                   'Filesystem OS type': '-o',
                   'Filesystem revision #': '-r',
                   'Filesystem volume name': '-L',
                   'Flex block group size': '-G',
                   'Fragment size': '-f',
                   'Inode count': '-i',
                   'Inode size': '-I',
                   'Journal inode': '-j',
                   'Reserved block count': '-m'}

    conversions = {
        'Journal inode': lambda d, k: None,
        'Filesystem volume name': __volume_name,
        'Reserved block count': __block_count,
        'Inode count': __inode_count,
        'Filesystem features': lambda d, k: re.sub(' ', ',', d[k]),
        'Filesystem revision #': lambda d, k: d[k][0]}

    for key, value in ext_mapping.iteritems():
        if key not in tune2fs_dict:
            continue
        if key in conversions:
            mkfs_option[value] = conversions[key](tune2fs_dict, key)
        else:
            mkfs_option[value] = tune2fs_dict[key]


def xfs_tunables(dev):
    """Call xfs_grow -n to get filesystem tunables."""
    # Have to mount the filesystem to call xfs_grow.
    tmp_mount_dir = tempfile.mkdtemp()
    cmd = 'mount %s %s' % (dev, tmp_mount_dir)
    utils.system_output(cmd)
    xfs_growfs = os.path.join(os.environ['AUTODIR'], 'tools', 'xfs_growfs')
    cmd = '%s -n %s' % (xfs_growfs, dev)
    try:
        out = utils.system_output(cmd)
    finally:
        # Clean.
        cmd = 'umount %s' % dev
        utils.system_output(cmd, ignore_status=True)
        os.rmdir(tmp_mount_dir)

    ## The output format is given in report_info (xfs_growfs.c)
    ## "meta-data=%-22s isize=%-6u agcount=%u, agsize=%u blks\n"
    ## "                 =%-22s sectsz=%-5u attr=%u\n"
    ## "data         =%-22s bsize=%-6u blocks=%llu, imaxpct=%u\n"
    ## "                 =%-22s sunit=%-6u swidth=%u blks\n"
    ## "naming     =version %-14u bsize=%-6u\n"
    ## "log            =%-22s bsize=%-6u blocks=%u, version=%u\n"
    ## "                 =%-22s sectsz=%-5u sunit=%u blks, lazy-count=%u\n"
    ## "realtime =%-22s extsz=%-6u blocks=%llu, rtextents=%llu\n"

    tune2fs_dict = {}
    # Flag for extracting naming version number
    keep_version = False
    for line in out.splitlines():
        m = re.search('^([-\w]+)', line)
        if m:
            main_tag = m.group(1)
        pairs = line.split()
        for pair in pairs:
            # naming: version needs special treatment
            if pair == '=version':
                # 1 means the next pair is the version number we want
                keep_version = True
                continue
            if keep_version:
                tune2fs_dict['naming: version'] = pair
                # Resets the flag since we have logged the version
                keep_version = False
                continue
            # Ignores the strings without '=', such as 'blks'
            if '=' not in pair:
                continue
            key, value = pair.split('=')
            tagged_key = '%s: %s' % (main_tag, key)
            if re.match('[0-9]+', value):
                tune2fs_dict[tagged_key] = int(value.rstrip(','))
            else:
                tune2fs_dict[tagged_key] = value.rstrip(',')

    return tune2fs_dict


def xfs_mkfs_options(tune2fs_dict, mkfs_option):
    """Maps filesystem tunables to their corresponding mkfs options."""

    # Mappings
    xfs_mapping = {'meta-data: isize': '-i size',
                   'meta-data: agcount': '-d agcount',
                   'meta-data: sectsz': '-s size',
                   'meta-data: attr': '-i attr',
                   'data: bsize': '-b size',
                   'data: imaxpct': '-i maxpct',
                   'data: sunit': '-d sunit',
                   'data: swidth': '-d swidth',
                   'data: unwritten': '-d unwritten',
                   'naming: version': '-n version',
                   'naming: bsize': '-n size',
                   'log: version': '-l version',
                   'log: sectsz': '-l sectsize',
                   'log: sunit': '-l sunit',
                   'log: lazy-count': '-l lazy-count',
                   'realtime: extsz': '-r extsize',
                   'realtime: blocks': '-r size',
                   'realtime: rtextents': '-r rtdev'}

    mkfs_option['-l size'] = tune2fs_dict['log: bsize'] * (
        tune2fs_dict['log: blocks'])

    for key, value in xfs_mapping.iteritems():
        mkfs_option[value] = tune2fs_dict[key]


def compare_features(needed_feature, current_feature):
    """Compare two ext* feature lists."""
    if len(needed_feature) != len(current_feature):
        return False
    for feature in current_feature:
        if feature not in needed_feature:
            return False
    return True


def match_ext_options(fs_type, dev, needed_options):
    """Compare the current ext* filesystem tunables with needed ones."""
    # mkfs.ext* will load default options from /etc/mke2fs.conf
    conf_opt = parse_mke2fs_conf(fs_type)
    # We need to convert the conf options to mkfs options.
    conf_mkfs_opt = convert_conf_opt(conf_opt)
    # Breaks user mkfs option string to dictionary.
    needed_opt_dict = opt_string2dict(needed_options)
    # Removes ignored options.
    ignored_option = ['-c', '-q', '-E', '-F']
    for opt in ignored_option:
        if opt in needed_opt_dict:
            del needed_opt_dict[opt]

   # User options override config options.
    needed_opt = conf_mkfs_opt
    for key, value in needed_opt_dict.iteritems():
        if key == '-N' or key == '-T':
            raise Exception('-N/T is not allowed.')
        elif key == '-O':
            needed_opt[key] = merge_ext_features(needed_opt[key], value)
        else:
            needed_opt[key] = value

    # '-j' option will add 'has_journal' feature.
    if '-j' in needed_opt and 'has_journal' not in needed_opt['-O']:
        needed_opt['-O'].append('has_journal')
    # 'extents' will be shown as 'extent' in the outcome of tune2fs
    if 'extents' in needed_opt['-O']:
        needed_opt['-O'].append('extent')
        needed_opt['-O'].remove('extents')
    # large_file is a byproduct of resize_inode.
    if 'large_file' not in needed_opt['-O'] and (
        'resize_inode' in needed_opt['-O']):
        needed_opt['-O'].append('large_file')

    current_opt = {}
    tune2fs_dict = ext_tunables(dev)
    ext_mkfs_options(tune2fs_dict, current_opt)

    # Does the match
    for key, value in needed_opt.iteritems():
        if key == '-O':
            if not compare_features(value, current_opt[key].split(',')):
                return False
        elif key not in current_opt or value != current_opt[key]:
            return False
    return True


def match_xfs_options(dev, needed_options):
    """Compare the current ext* filesystem tunables with needed ones."""
    tmp_mount_dir = tempfile.mkdtemp()
    cmd = 'mount %s %s' % (dev, tmp_mount_dir)
    utils.system_output(cmd)
    xfs_growfs = os.path.join(os.environ['AUTODIR'], 'tools', 'xfs_growfs')
    cmd = '%s -n %s' % (xfs_growfs, dev)
    try:
        current_option = utils.system_output(cmd)
    finally:
        # Clean.
        cmd = 'umount %s' % dev
        utils.system_output(cmd, ignore_status=True)
        os.rmdir(tmp_mount_dir)

    # '-N' has the same effect as '-n' in mkfs.ext*. Man mkfs.xfs for details.
    cmd = 'mkfs.xfs %s -N -f %s' % (needed_options, dev)
    needed_out = utils.system_output(cmd)
    # 'mkfs.xfs -N' produces slightly different result than 'xfs_growfs -n'
    needed_out = re.sub('internal log', 'internal    ', needed_out)
    if current_option == needed_out:
        return True
    else:
        return False


def match_mkfs_option(fs_type, dev, needed_options):
    """Compare the current filesystem tunables with needed ones."""
    if fs_type.startswith('ext'):
        ret = match_ext_options(fs_type, dev, needed_options)
    elif fs_type == 'xfs':
        ret = match_xfs_options(dev, needed_options)
    else:
        ret = False

    return ret
