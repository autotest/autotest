import os, sys, dircache, string, re

def check_python_version():
	version = string.split(string.split(sys.version)[0], ".")
	version = [version[0], version[1]]
	if map(int, version) < [2, 4]:
		print "Python 2.4 or newer is needed"
		sys.exit(1)

def atcc_list_control_files(test_type, at_dir):
	dir_ls = dircache.listdir(at_dir + '/' + test_type)
	u = []
	for i in dir_ls:
		if i != ".svn":
			dir_ls2 = dircache.listdir(at_dir + '/' + test_type + '/' + i)
			for j in dir_ls2:
				result = re.match("^control", j)
				if result != None:
					z = str(i + "/" + j)
					k = z, "", 0
					u.append(k)

	return u

def atcc_control_file_read(tag, test_type, at_dir):
	file = (at_dir + '/' + test_type + '/' + tag)
	f = open(file, 'r')

	z = f.readline()
	z = z.lstrip("job.run_test(")
	z = z.rstrip('\n')
	z = z.rstrip(')')
	z = z.split(',')

	x = len(z)

	if x == 1:
		z = ""
	elif x > 1:
		z = z[1:]
		m = ""
		for i in z:
			m += (',' + i)

		m = m.lstrip(',')
		m = m.strip()
		z = str(m)

	f.close()

	return z

def atcc_setup_tmp_dirs_files(menu_dir):
	if not os.path.isdir(menu_dir + '/tmp/'):
		os.mkdir(menu_dir + '/tmp/')
	if os.path.isfile(menu_dir + '/tmp/Tests results'):
		os.remove(menu_dir + '/tmp/Tests results')
	if os.path.isfile(menu_dir + '/tmp/Possible kernel memory leaks'):
		os.remove(menu_dir + '/tmp/Possible kernel memory leaks')

def atcc_save_results1(i, at_dir, menu_dir):
	if i != "":
		if os.path.isfile(at_dir + '/results/default/' + i + '/debug/stderr'):
			os.system('cp ' + at_dir + '/results/default/' + i + '/debug/stderr ' + menu_dir + '/tmp/' + i + '.stderr')
		if os.path.isfile(at_dir + '/results/default/' + i + '/debug/stdout'):
			os.system('cp ' + at_dir + '/results/default/' + i + '/debug/stdout ' + menu_dir + '/tmp/' + i + '.stdout')
	if os.path.isfile(at_dir + '/results/default/status'):
		os.system('cat ' + at_dir + '/results/default/status >> ' + menu_dir + '/tmp/Tests\ results')
	if os.path.isfile('/sys/kernel/debug/memleak'):
		print "Saving possible kernel memory leaks"
		os.system('echo "' + i + '" >> ' + menu_dir + '/tmp/Possible kernel memory leaks')
		os.system('cat /sys/kernel/debug/memleak >> ' + menu_dir + '/tmp/Possible kernel memory leaks')

def atcc_save_profilers_results(i, j, at_dir, menu_dir):
	if os.path.isfile(at_dir + '/results/default/' + j + '.' + i + '/profiling/monitor'):
		os.system('cp ' + at_dir + '/results/default/' + j + '.' + i + '/profiling/monitor ' + menu_dir + '/tmp/' + j + '.monitor')
	if os.path.isfile(at_dir + '/results/default/' + j + '.' + i + '/profiling/oprofile.kernel'):
		os.system('cp ' + at_dir + '/results/default/' + j + '.' + i + '/profiling/oprofile.kernel ' + menu_dir + '/tmp/' + j + '.oprofile.kernel')
	if os.path.isfile(at_dir + '/results/default/' + j + '.' + i + '/profiling/oprofile.user'):
		os.system('cp ' + at_dir + '/results/default/' + j + '.' + i + '/profiling/oprofile.user ' + menu_dir + '/tmp/' + j + '.oprofile.user')

def atcc_save_results2(res1, res2, at_dir, menu_dir):
	if os.path.isfile(at_dir + '/results/default/status'):
		os.system('cat ' + at_dir + '/results/default/status >> ' + menu_dir + '/tmp/Tests\ results')

	for i in res1:
		for j in res2:
			atcc_save_profilers_results(i, j, at_dir, menu_dir)
