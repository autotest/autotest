#!/usr/bin/python
# perf_graphs.cgi: generate web page showing multiple graphs of benchmarks' performance

import cgi, cgitb

benchmark_main_metrics = {
	'dbench'   : 'throughput',
	'kernbench': '1000/elapsed',
	'membench' : 'sweeps',
	'tbench'   : 'throughput',
	'unixbench': 'score',
	}  # keep sync'd with similar table in perf_graph.cgi


def multiple_graphs_page():
	# Generate html for web page showing graphs for all benchmarks
	# Each graph image is formed by an invocation of 2nd cgi file  
	print "Content-Type: text/html\n"
	print "<html><body>"
	print "<h3> All kernel performance benchmark runs"
	if one_user:
		print "by user", one_user
	if machine_names:
		print ", on selected"
	else:
		print ", on all test"
	print "machines </h3>"
	if one_user != 'yinghan':
		print "Uncontrolled results!"
		print "Not using just the controlled benchmarking machines."
		print "All variants of a platform type (mem size, # disks, etc) are"
		print "lumped together."
		print "Non-default test args may have been applied in some cases."
	print "No-container cases and whole-machine single-container cases"
	print "are lumped together." 
	for bench in benchmark_main_metrics:
		print "<h2>", bench.capitalize(), ": </h2>"
		args = ['benchmark=%s' % bench]
		if one_user:
			args.append('user=%s' % one_user)
		if one_platform:
			args.append('platform=%s' % one_platform)
		if machine_names:
			args.append('machines=%s' % machine_names)
		print "<img src='perf_graph.cgi?%s'>" % '&'.join(args)
	print "</body></html>"


cgitb.enable()
form = cgi.FieldStorage()
one_platform  = form.getvalue('platform', None)
one_user      = form.getvalue('user',     None)
machine_names = form.getvalue('machines', None)
multiple_graphs_page()

