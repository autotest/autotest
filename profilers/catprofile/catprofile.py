# sets up a subprocess to cat a file on a specified interval
# really, really ought to autoswitch on a list of files or individual file
import profiler, time

class catprofile(profiler.profiler):
	version = 1

	def setup(self, filenames, output_filename, interval = 5):
		self.filenames = filenames
		# THIS IS WRONG. output should go under a test
		self.output = self.job.resultdir + '/' + output_filename
		self.interval = interval


	def start(self):
		self.child_pid = os.fork()
		if self.child_pid:			# parent
			return None
		else:					# child
			lines = []
			for file in self.filenames:
				input = open(filename, 'r')
				lines = lines + input.readlines()
				input.close
			output = open(self.output, 'w+')
			output.write(time.asctime() + '\n')
			output.write('----------\n')
			output.writelines(lines)
			output.write('==========\n')
			output.close()
			time.sleep(self.interval)
			

	def stop(self):
		os.kill(self.child_pid, SIGTERM)


	def report(self):
		return None

