"""
Sample configuration file for the "mirror" script that will use
rsync://rsync.kernel.org to fetch a kernel file list and schedule jobs on new
kernel releases.

This file has to be valid python code executed by the "mirror" script. The file
may define and do anything but the following "names" are special:

- a global name "source" is expected to implement get_new_files() method which
will be used by "mirror" to fetch the list of new files

- an optional global iteratable of regular expression strings named
"filter_exprs" where for each regular expression if there is a match group
named "arg" then the original kernel filename will be replaced with the
contents of that group; if no such match group is defined then all the filename
will be considered (if there is at least one regular expression that matches
the filename, otherwise the filename is just filtered out); if "filter_exprs"
is not defined (or defined to be empty) then no filtering is performed

- an optional "trigger" instance of a trigger class; by default this is
initialized with trigger.trigger() but you can set it to another instance
(of your own site specific trigger class); even if you don't set it you
most certainly want to add a couple of actions to the trigger instance to
be executed for the new kernels (by default the list is empty and nothing
will happen with the new kernels other than being included in the known
kernels database so future lookups will not consider them new again)
"""
from autotest_lib.mirror import database, source as source_module
from autotest_lib.mirror import trigger as trigger_module

# create a database object where to store information about known files
db = database.dict_database('rsync.kernel.org.db')

# create a source object that will be used to fetch the list of new kernel
# files (this example uses rsync_source)
source = source_module.rsync_source(db,
    'rsync://rsync.kernel.org/pub/linux/kernel',
    excludes=('2.6.0-test*/', 'broken-out/', '*.sign', '*.gz'))
source.add_path('v2.6/patch-2.6.*.bz2', 'v2.6')
source.add_path('v2.6/linux-2.6.[0-9].tar.bz2', 'v2.6')
source.add_path('v2.6/linux-2.6.[0-9][0-9].tar.bz2', 'v2.6')
source.add_path('v2.6/testing/patch*.bz2', 'v2.6/testing')
source.add_path('v2.6/snapshots/*.bz2', 'v2.6/snapshots')
source.add_path('people/akpm/patches/2.6/*', 'akpm')

# Given a list of files filter and transform it for entries that look like
# legitimate releases (may be empty in which case no filtering/transformation
# is done). If you want to replace the matched filename to only a part of it
# put the part you want extracted in a match group named "arg".
filter_exprs = (
    # The major tarballs
    r'^(.*/)?linux-(?P<arg>2\.6\.\d+)\.tar\.bz2$',
    # Stable releases
    r'^(.*/)?patch-(?P<arg>2\.6\.\d+\.\d+)\.bz2$',
    # -rc releases
    r'^(.*/)?patch-(?P<arg>2\.6\.\d+-rc\d+)\.bz2$',
    # -git releases
    r'^(.*/)?patch-(?P<arg>2\.6\.\d+(-rc\d+)?-git\d+)\.bz2$',
    # -mm tree
    r'^(.*/)?(?P<arg>2\.6\.\d+(-rc\d+)?-mm\d+)\.bz2$',
    )

# associate kernel versions with kernel config files
# all machines have the same hardware configuration so they will all
# use the same mapping for kernel version -> kernel config file
_common_kernel_config = {
    '2.6.20': '/path/to/2.6.20.config',
    '2.6.25': '~/kernel-2.6.25.config',
    '2.6.29': 'http://somesite/configs/2.6.29.conf',
    }

# a mapping of machine -> machine_info (containing list a of control filenames
# and kernel version association to kernel config filenames)
_control_map = {
    'mach1': trigger_module.map_action.machine_info(
            ('/path/to/control1', '~/control2.srv'), _common_kernel_config),
    'mach2': trigger_module.map_action.machine_info(
            ('/path/to/control1',), _common_kernel_config),
    'mach3': trigger_module.map_action.machine_info(
            ('/path/to/control3',), _common_kernel_config),
    'mach4': trigger_module.map_action.machine_info(
            ('/path/to/control4',), _common_kernel_config),
    }

# no need to instantiate trigger_module.trigger() as it's already done so
# trigger = trigger_module.trigger()

# now register some trigger actions otherwise nothing will be done for the new
# kernel versions
trigger.add_action(trigger_module.map_action(_control_map, 'kerntest-%s'))
trigger.add_action(trigger_module.email_action('test@test.com'))
