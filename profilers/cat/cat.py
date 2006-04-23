# sets up a subprocess to cat a file on a specified interval
# really, really ought to autoswitch on a list of files or individual files
import time

class readprofile(profiler.profiler):
	version = 1

# http://www.kernel.org/pub/linux/utils/util-linux/util-linux-2.12r.tar.bz2
	def setup(self):
		return None


	def start(self, filename, output_filename, interval = 5):
		self.child_pid = os.fork()
		if self.child_pid:			# parent
			return None
		else:					# child
			input = open(filename, 'r')
			lines = input.readlines()
			input.close
			output = open(output_filename, 'w')
			output.write(time.asctime() + '\n')
			output.write('----------\n')
			output.writelines(lines)
			output.write('==========\n')
			output.close()
			time.sleep(interval)
			

	def stop(self):
		os.kill(self.child_pid, SIGTERM)


	def report(self):
		return None

