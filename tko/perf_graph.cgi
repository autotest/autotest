#!/usr/bin/python
# perf_graph.cgi: generate image of one graph of a benchmark's performance

__author__ = """duanes@google.com (Duane Sand), Copyright Google 2008"""

import cgi, cgitb, datetime, re
import common
from autotest_lib.tko import db, plotgraph  
from autotest_lib.client.bin import kernel_versions

kernel_names = {}
kernel_dates = {}
kernel_sortkeys = {}
machine_to_platform = {}
selected_machines = ''
selected_jobs = set()
use_all_jobs = True

benchmark_main_metrics = {
	'dbench'   : 'throughput',
	'kernbench': '1000/elapsed',
	'membench' : 'sweeps',
	'tbench'   : 'throughput',
	'unixbench': 'score',
	}  # keep sync'd with similar table in perf_graphs.cgi

usual_platforms = ['Icarus', 'Argo', 'Ilium', 'Warp19', 'Warp18', 'Unicorn']

date_unknown = datetime.datetime(2999, 12, 31, 23, 59, 59)


def get_all_kernel_names():
	# lookup all kernel names once, and edit for graph axis
	nrows = db.cur.execute('select kernel_idx, printable from kernels')
	for idx, name in db.cur.fetchall():
		sortname = kernel_versions.version_encode(name)
		name = name.replace('-smp-', '-')     # boring, in all names
		name = name.replace('2.6.18-2', '2')  # reduce clutter 
		kernel_names[idx] = name
		kernel_dates[name] = date_unknown
		kernel_sortkeys[name] = sortname


def kname_to_sortkey(kname):
	# cached version of version_encode(uneditted name)
	return kernel_sortkeys[kname]


def sort_kernels(kernels):
	return sorted(kernels, key=kname_to_sortkey)


def get_all_platform_info():
	# lookup all machine/platform info once
	global selected_machines
	machs = []
	cmd =  'select machine_idx, machine_group from machines'
	if selected_machine_names:
		# convert 'a,b,c' to '("a","b","c")'
		hnames = selected_machine_names.split(',')
		hnames = ['"%s"' % name for name in hnames]
		cmd += ' where hostname in (%s)' % ','.join(hnames)
	nrows = db.cur.execute(cmd)
	for idx, platform in db.cur.fetchall():
		# ignore machine variations in 'mobo_memsize_disks'
		machine_to_platform[idx] = platform.split('_', 2)[0]
		machs.append(str(idx))
	if selected_machine_names:
		selected_machines = ','.join(machs)


def get_selected_jobs():
	global use_all_jobs
	use_all_jobs = not( one_user or selected_machine_names )
	if use_all_jobs:
		return
	needs = []
	if selected_machine_names:
		needs.append('machine_idx in (%s)' % selected_machines)
	if one_user:
		needs.append('username = "%s"' % one_user)
	cmd = 'select job_idx from jobs where %s' % ' and '.join(needs)
	nrows = db.cur.execute(cmd)
	for row in db.cur.fetchall():
		job_idx = row[0]
		selected_jobs.add(job_idx)


def identify_relevent_tests(benchmark, platforms):
	# Collect idx's for all whole-machine test runs of benchmark
	# Also collect earliest test dates of kernels used

        cmd = 'select status_idx from status where word = "GOOD"'
        nrows = db.cur.execute(cmd)
        good_status = db.cur.fetchall()[0][0]

	tests = {}
	cmd = ( 'select test_idx, test, kernel_idx, machine_idx,' 
		' finished_time, job_idx, status from tests'
		' where test like "%s%%"' % benchmark )
	if selected_machine_names:
		cmd +=  ' and machine_idx in (%s)' % selected_machines
	nrows = db.cur.execute(cmd)
	for row in db.cur.fetchall():
		(test_idx, tname, kernel_idx, 
			machine_idx, date, job_idx, status) = row
		kname = kernel_names[kernel_idx]
		if date:
			kernel_dates[kname] = min(kernel_dates[kname], date)
		# omit test runs from failed runs
		#   and from unwanted platforms
		#   and from partial-machine container tests
		#   and from unselected machines or users
		platform = machine_to_platform[machine_idx]
		if ( status == good_status     and
		     platform in platforms     and
		     tname.find('.twoway') < 0 and
		     (use_all_jobs or job_idx in selected_jobs) ):
			tests.setdefault(platform, {})
			tests[platform].setdefault(kname, [])
			tests[platform][kname].append(test_idx)
	return tests


def prune_old_kernels():
	# reduce clutter of graph and improve lookup times by pruning away
	#   older experimental kernels and oldest release-candidate kernels
	today = datetime.datetime.today()
	exp_cutoff = today - datetime.timedelta(weeks=7)
	rc_cutoff  = today - datetime.timedelta(weeks=18)
	kernels_forgotten = set()
	for kname in kernel_dates:
		date = kernel_dates[kname]
		if ( date == date_unknown or
		    (date < exp_cutoff and not kernel_versions.is_release_candidate(kname)) or
		    (date < rc_cutoff  and not kernel_versions.is_released_kernel(kname)  )   ):
			kernels_forgotten.add(kname)
	return kernels_forgotten


def get_metric_at_point(tests, metric):
	nruns = len(tests)
	if metric == 'good_testrun_count':
		return [nruns]

	# take subsamples from largest sets of test runs
	min_sample_size = 100  # enough to approx mean & std dev
	decimator = int(nruns / min_sample_size)
	if decimator > 1:
		tests = [tests[i] for i in xrange(0, nruns, decimator)]
	# have  min_sample_size <= len(tests) < min_sample_size*2

	invert_scale = None
	if metric.find('/') > 0:
		invert_scale, metric = metric.split('/', 1)
		invert_scale = float(invert_scale)
		# 1/  gives simple inversion of times to rates,
		# 1000/  scales Y axis labels to nice integers

	if not tests:
		return []
	tests = ','.join(str(idx) for idx in tests)
	cmd = ( 'select value from iteration_result'
		' where test_idx in (%s) and attribute = "%s"'
		% ( tests, metric) )
	nrows = db.cur.execute(cmd)
	vals = [row[0] for row in db.cur.fetchall()]
	if invert_scale:
		vals = [invert_scale/v for v in vals]
	return vals


def collect_test_results(possible_tests, kernels_forgotten, metric):
	# collect selected metric of all test results for covered
	#   combo's of platform and kernel
	data = {}
	for platform in possible_tests:
		for kname in possible_tests[platform]:
			if kname in kernels_forgotten:
				continue
			vals = get_metric_at_point(
					possible_tests[platform][kname], metric)
			if vals:
				data.setdefault(platform, {})
				data[platform].setdefault(kname, [])
				data[platform][kname] += vals
	return data


def one_performance_graph(benchmark, metric=None, one_platform=None):
	# generate image of graph of one benchmark's performance over
	#    most kernels (X axis) and all machines (one plotline per type)
	if one_platform:
		platforms = [one_platform]
	else:
		platforms = usual_platforms
	if not benchmark:
		benchmark = 'dbench'
	if not metric:
		metric = benchmark_main_metrics[benchmark]

	get_all_kernel_names()
	get_all_platform_info()
	get_selected_jobs()
	possible_tests = identify_relevent_tests(benchmark, platforms)
	kernels_forgotten = prune_old_kernels()
	data = collect_test_results(possible_tests, kernels_forgotten, metric)

	if data.keys():
		title = benchmark.capitalize()
		if one_user:
			title += " On %s's Runs" % one_user
		if selected_machine_names:
			title += " On Selected Machines " + selected_machine_names
		else:
			title += " Over All Machines"
		graph = plotgraph.gnuplot(title, 'Kernels', 
				metric.capitalize(), xsort=sort_kernels, 
				size='1000,600' )
		for platform in platforms:
			if platform in data:
				graph.add_dataset(platform, data[platform])
		graph.plot(cgi_header = True)
	else:
		# graph has no data; avoid plotgraph and Apache complaints
		print "Content-type: image/gif\n"
		print file("blank.gif", "rb").read()


cgitb.enable()
form = cgi.FieldStorage()
one_platform  = form.getvalue('platform',  None)
benchmark     = form.getvalue('benchmark', None)
metric        = form.getvalue('metric',    None)
one_user      = form.getvalue('user',      '')
selected_machine_names = form.getvalue('machines', '')
if selected_machine_names == 'yinghans':
	selected_machine_names = 'ipbj8,prik6,bdcz12'
db = db.db()
one_performance_graph(benchmark, metric, one_platform)

