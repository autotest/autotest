#!/usr/bin/python
print "Content-type: text/html\n"
import cgi, cgitb, os, sys, re
sys.stdout.flush()
cgitb.enable()

tko = os.path.dirname(os.path.realpath(os.path.abspath(sys.argv[0])))
sys.path.insert(0, tko)
import db, display, frontend

db = db.db()

def main():
	form = cgi.FieldStorage()

	kernel_idx = form['kernel'].value
	kernel = frontend.kernel.select(db, {'kernel_idx' : kernel_idx })[0]

	if form.has_key('machine'):
		machines = []
		for idx in form['machine'].value.split(','):
			where = { 'machine_idx' : idx }
			machines.append(frontend.machine.select(db, where)[0])
	elif form.has_key('group'):
		where = { 'machine_group' : form['group'].value }
		machines = frontend.machine.select(db, where)

	if form.has_key('test'):
		test = form['test'].value
	else:
		test = None

	if len(machines) == 1:
		print_jobs_vs_tests(machines[0], kernel, test)
	else:
		print_jobs_vs_machines(machines, kernel, test)


def print_jobs_vs_tests(machine, kernel, only_test):
	# first we have to get a list of all run tests
	results = {}         # will be a 2d hash on [testname][jobname]
	all_tests = set([])
	all_jobs = set([])
	where = { 'kernel_idx':kernel.idx , 'machine_idx':machine.idx }
	if only_test:
		where['subdir'] = only_test
	tests = frontend.test.select(db, where)
	for test in tests:
		all_tests.add(test.testname)
		all_jobs.add(test.job.tag)
		if not results.has_key(test.testname):
			results[test.testname] = {}
		results[test.testname][test.job.tag] = test
	test_list = sorted(list(all_tests))
	job_list = sorted(list(all_jobs))

	print '<h1>Kernel: %s</h1>\n' % kernel.printable
	print '<h1>Machine: %s</h1>\n' % machine.hostname

	header_row = [ display.box('Job', header=True) ]
	for jobname in job_list:
		header_row.append( display.box(jobname, header=True) )

	matrix = [header_row]
	for testname in test_list:
		if not results.has_key(testname):
			continue
		row = [display.box(testname)]
		for jobname in job_list:
			test = results[testname].get(jobname, None)
			if test:
				box = display.box(test.status_word,
						color_key = test.status_word,
						link = test.url)
			else:
				box = display.box(None)
			row.append(box)
		matrix.append(row)
	matrix.append(header_row)

	display.print_table(matrix)


def print_jobs_vs_machines(machines, kernel, only_test):
	if not only_test:
		raise "No test specified!"
	results = {}         # will be a 2d hash [machine][jobname]
	all_jobs = set([])
	for machine in machines:
		where = { 'kernel_idx':kernel.idx , 'machine_idx':machine.idx,
			  'subdir':only_test }
		tests = frontend.test.select(db, where)
		if tests:
			results[machine] = {}
		for test in tests:
			results[machine][test.job.tag] = test
			all_jobs.add(test.job.tag)
		results[machine.idx] = tests
	job_list = sorted(list(all_jobs))

	print '<h1>Kernel: %s</h1>\n' % kernel.printable
	print '<h1>Test: %s</h1>\n' % only_test

	header_row = [ display.box('Machine', header=True) ]
	for jobname in job_list:
		header_row.append( display.box(jobname, header=True) )

	matrix = [header_row]
	for machine in machines:
		if not results.has_key(machine):
			continue
		tests = results[machine]
		row = [display.box(machine.hostname)]
		for jobname in job_list:
			test = results[machine].get(jobname, None)
			if test:
				box = display.box(test.status_word,
						color_key = test.status_word,
						link = test.url)
			else:
				box = display.box(None)
			row.append(box)
		matrix.append(row)
	matrix.append(header_row)

	display.print_table(matrix)


main()
#!/usr/bin/python
print "Content-type: text/html\n"
import cgi, cgitb, os, sys, re
sys.stdout.flush()
cgitb.enable()

tko = os.path.dirname(os.path.realpath(os.path.abspath(sys.argv[0])))
sys.path.insert(0, tko)
import db, display, frontend

db = db.db()

def main():
	form = cgi.FieldStorage()

	kernel_idx = form['kernel'].value
	kernel = frontend.kernel.select(db, {'kernel_idx' : kernel_idx })[0]

	if form.has_key('machine'):
		machines = []
		for idx in form['machine'].value.split(','):
			where = { 'machine_idx' : idx }
			machines.append(frontend.machine.select(db, where)[0])
	elif form.has_key('group'):
		where = { 'machine_group' : form['group'].value }
		machines = frontend.machine.select(db, where)

	if form.has_key('test'):
		test = form['test'].value
	else:
		test = None

	if len(machines) == 1:
		print_jobs_vs_tests(machines[0], kernel, test)
	else:
		print_jobs_vs_machines(machines, kernel, test)


def print_jobs_vs_tests(machine, kernel, only_test):
	# first we have to get a list of all run tests
	all_tests = []
	results = {}         # will be a hash on [testname]
	where = { 'kernel_idx':kernel.idx , 'machine_idx':machine.idx }
	if only_test:
		where['subdir'] = only_test
	tests = frontend.test.select(db, where)
	for test in tests:
		results[test.testname] = test

	test_list = [test.testname for test in tests]
	test_list = display.sort_tests(list(set(test_list)))

	print '<h1>Kernel: %s</h1>\n' % kernel.printable
	print '<h1>Machine: %s</h1>\n' % machine.hostname

	header_row = [ display.box('Job', header=True) ]
	for test in tests:
		header_row.append( display.box(test.job.tag, header=True) )

	matrix = [header_row]
	for testname in test_list:
		if not results.has_key(testname):
			continue
		row = [display.box(testname)]
		for test in tests:
			box = display.box(test.status_word,
						color_key = test.status_word,
						link = test.url)
			row.append(box)
		matrix.append(row)
	matrix.append(header_row)

	display.print_table(matrix)


def print_jobs_vs_machines(machines, kernel, test):
	if not test:
		raise "No test specified!"
	results = {}         # will be a 2d hash [machine][jobname]
	all_jobs = set([])
	for machine in machines:
		where = { 'kernel_idx':kernel.idx , 'machine_idx':machine.idx,
			  'subdir':test }
		tests = frontend.test.select(db, where)
		print '<br><pre>%s\n%d\n%d\n%s\n%s</pre>' % (test, kernel.idx, machine.idx, machine.hostname, str(len(tests)))
		if tests:
			results[machine] = {}
		for test in tests:
			results[machine][test.job.tag] = test
			all_jobs.add(test.job.tag)
		results[machine.idx] = tests
	job_list = sorted(list(all_jobs))
	print '<pre>%s</pre>' % str(job_list)

	print '<h1>Kernel: %s</h1>\n' % kernel.printable
	print '<h1>Test: %s</h1>\n' % test.testname

	header_row = [ display.box('Machine', header=True) ]
	for jobname in job_list:
		header_row.append( display.box(jobname, header=True) )

	matrix = [header_row]
	for machine in machines:
		if not results.has_key(machine):
			continue
		tests = results[machine]
		row = [display.box(machine.hostname)]
		for jobname in job_list:
			if not results[machine].has_key(jobname):
				continue
			test = results[machine][jobname]
			box = display.box(test.status_word,
						color_key = test.status_word,
						link = test.url)
			row.append(box)
		matrix.append(row)
	matrix.append(header_row)

	display.print_table(matrix)


main()
