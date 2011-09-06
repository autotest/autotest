import datetime, logging, os, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class wb_kupdate(test.test):
    version = 1


    def _check_parameters(self, mount_point, write_size, file_count,
                          old_cleanup=False):
        """
        Check all test parameters.

        @param mount_point: the path to the desired mount_point.
        @param write_size: the size of data in MB to write.
        @param file_count: the number of files to write.
        @param old_cleanup: removes previous mount_point if it exists and is
                not mounted. Default is False.
        """
        # Check mount_point.
        if not os.path.exists(mount_point):
            logging.info('%s does not exist. Creating directory.', mount_point)
        elif not os.path.ismount(mount_point) and old_cleanup:
            logging.info('Removing previous mount_point directory')
            os.rmdir(mount_point)
            logging.info('Creating new mount_point.')
        else:
            raise error.TestError('Mount point: %s already exists.' %
                                  mount_point)

        os.makedirs(mount_point)
        # Check write_size > 0.
        if not (write_size > 0):
            raise error.TestError('Write size should be a positive integer.')

        # Check file_count > 0.
        if not (file_count > 0) :
            raise error.TestError('File count shoulde be a positive integer.')


    def _reset_device(self):
        """
        Reset the test. Reinitialize sparse file.
        """
        # Umount device.
        logging.debug('Cleanup - unmounting loopback device.')
        utils.system('umount %s' % self.mount_point, ignore_status=True)

        # Remove sparse_file.
        logging.debug('Cleanup - removing sparse file.')
        os.remove(self.sparse_file)

        # Remove mount_point directory.
        logging.debug('Cleanup - removing the mount_point.')
        os.rmdir(self.mount_point)


    def _create_partition(self):
        """
        Create and initialize the sparse file.
        """
        # Recreate sparse_file.
        utils.system('dd if=/dev/zero of=%s bs=1M seek=1024 count=1' %
                      self.sparse_file)

        # Format sparse_file.
        utils.system('echo "y" |  mkfs -t %s %s' %
                     (self.file_system, self.sparse_file))

        # Mount sparse_file.
        utils.system('mount -o loop -t %s %s %s' %
                     (self.file_system, self.sparse_file, self.mount_point))


    def _needs_more_time(self, start_time, duration, _now=None):
        """
        Checks to see if the test has run its course.

        @param start_time: a datetime object specifying the start time of the
                test.
        @param duration: test duration in minutes.
        @param _now: used mostly for testing - ensures that the function returns
                pass/fail depnding on the value of _now.

        @return: True if the test still needs to run longer.
                 False if the test has run for 'duration' minutes.
        """
        if not _now:
            time_diff = datetime.datetime.now() - start_time
        else:
            time_diff = _now - start_time
        return time_diff <= datetime.timedelta(seconds=duration*60)


    def _write_data(self, destination, counter, write_size):
        """
        Writes data to the cache/memory.

        @param destination: the absolute path to where the data needs to be
        written.
        @param counter: the file counter.
        @param write_size: the size of data to be written.

        @return: the time when the write completed as a datetime object.
        """
        # Write data to disk.
        file_name = os.path.join(destination, 'test_file_%s' % counter)
        write_cmd = ('dd if=/dev/zero of=%s bs=1M count=%s' %
                     (file_name, write_size))
        utils.system(write_cmd)

        # Time the write operation.
        write_completion_time = datetime.datetime.now()

        # Return write completion time.
        return write_completion_time


    def _get_disk_usage(self, file_name):
        """
        Returns the disk usage of given file.

        @param file_name: the name of the file.

        @return: the disk usage as an integer.
        """
        # Check du stats.
        cmd = '%s %s' % (self._DU_CMD, file_name)

        # Expected value for  output = '1028\tfoo'
        output = utils.system_output(cmd)

        # Desired ouput = (1028, foo)
        output = output.split('\t')

        return int(output[0])


    def _wait_until_data_flushed(self, start_time, max_wait_time):
        """
        Check to see if the sparse file size increases.

        @param start_time: the time when data was actually written into the
                cache.
        @param max_wait_time: the max amount of time to wait.

        @return: time waited as a datetime.timedelta object.
        """
        current_size = self._get_disk_usage(self.sparse_file)
        flushed_size = current_size

        logging.debug('current_size: %s' % current_size)
        logging.debug('flushed_size: %s' % flushed_size)

        # Keep checking until du value changes.
        while current_size == flushed_size:
            # Get flushed_size.
            flushed_size = self._get_disk_usage(self.sparse_file)
            logging.debug('flushed_size: %s' % flushed_size)
            time.sleep(1)

            # Check if data has been synced to disk.
            if not self._needs_more_time(start_time, max_wait_time):
                raise error.TestError('Data not flushed. Waited for %s minutes '
                                      'for data to flush out.' % max_wait_time)

        # Return time waited.
        return datetime.datetime.now() - start_time


    def initialize(self):
        """
        Initialize all private and global member variables.
        """
        self._DU_CMD = 'du'
        self.partition = None
        self.mount_point = ''
        self.sparse_file = ''
        self.result_map = {}
        self.file_system = None


    def run_once(self, mount_point, file_count, write_size,
                 max_flush_time=1, file_system=None, remove_previous=False,
                 sparse_file=os.path.join(os.getcwd(),'sparse_file'),
                 old_cleanup=False):
        """
        Control execution of the test.

        @param mount_point: the absolute path to the mount point.
        @param file_count: the number of files to write.
        @param write_size: the size of each file in MB.
        @param max_flush_time: the maximum time to wait for the writeback to
                flush dirty data to disk. Default = 1 minute.
        @param file_system: the new file system to be mounted, if any.
                Default = None.
        @param remove_previous: boolean that allows the removal of previous
                files before creating a new one. Default = False.
        @param sparse_file: the absolute path to the sparse file.
        @param old_cleanup: removes previous mount_point if it exists and is
                not mounted. Default is False.
        """
        # Check validity of parameters.
        self._check_parameters(mount_point, write_size, file_count,
                               old_cleanup)

        # Initialize class variables.
        self.mount_point = mount_point
        self.sparse_file = sparse_file
        self.file_system = file_system

        # Initialize partition values.
        self._create_partition()

        # Flush read and write cache.
        utils.drop_caches()

        # Start iterations.
        logging.info('Starting test operations.')
        test_start_time = datetime.datetime.now()
        counter = 1

        # Run test until file_count files are successfully written to disk.
        while counter < file_count:
            logging.info('Iteration %s.', counter)

            # Write data to disk.
            write_completion_time = self._write_data(self.mount_point, counter,
                                                     write_size)
            logging.debug('Write time:%s',
                          write_completion_time.strftime("%H:%M:%S"))

            # Wait until data get synced to disk.
            time_taken = self._wait_until_data_flushed(write_completion_time,
                                                       max_flush_time)

            # Log time statistics.
            logging.info('Time taken to flush data: %s seconds.',
                         time_taken.seconds)

            # Check if there is a need to remove the previously written file.
            if remove_previous:
                logging.debug('Removing previous file instance.')
                os.remove(sparse_file)
            else:
                logging.debug('Not removing previous file instance.')

            # Flush cache.
            logging.debug('Flush cache between iterations.')
            utils.drop_caches()

           # Update the result map.
            self.result_map[counter] = time_taken.seconds

            # Increment the counter.
            counter += 1


    def postprocess(self):
        """
        Cleanup routine.
        """
        # Write out keyval map.
        self.write_perf_keyval(self.result_map)

        # Cleanup device.
        self._reset_device()

        logging.info('Test operations completed.')
