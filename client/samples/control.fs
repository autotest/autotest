AUTHOR = "Autotest Team <autotest@test.kernel.org>"
TIME = "MEDIUM"
NAME = "Sample - Filesystem tests with different filesystems"
TEST_TYPE = "client"
TEST_CLASS = "Kernel"
TEST_CATEGORY = "Functional"

DOC = """
Runs a series of filesystem tests on a loopback partition using different
filesystem types. his shows some features of the job.partition method, such as
creating loopback partitions instead of using real disk partitions, looping.
"""

partition = job.partition('/tmp/looped', 1024, job.tmpdir)
# You can use also 'real' partitions, just comment the above and uncomment
# the below
#partition = job.partition('/dev/sdb1', job.tmpdir)

def test_fs():
    partition.mkfs(fstype)
    partition.mount()
    try:
        job.run_test('fsx', dir=partition.mountpoint, tag=fstype)
        job.run_test('iozone', dir=partition.mountpoint, tag=fstype)
        job.run_test('dbench', dir=partition.mountpoint, tag=fstype)
    finally:
        partition.unmount()
        partition.fsck()


for fstype in ('ext2', 'ext3', 'jfs', 'xfs', 'reiserfs'):
    job.run_group(test_fs)
