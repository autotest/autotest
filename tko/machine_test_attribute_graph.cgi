#!/usr/bin/python

# http://test.kernel.org/perf/kernbench.elm3b6.png

import cgi, cgitb, os, sys, re, subprocess
cgitb.enable()
Popen = subprocess.Popen

tko = os.path.dirname(os.path.realpath(os.path.abspath(sys.argv[0])))
sys.path.insert(0, tko)
import db, display, frontend, plotgraph
client_bin = os.path.abspath(os.path.join(tko, '../client/bin'))
sys.path.insert(0, client_bin)
import kernel_versions

db = db.db()

def main():
	form = cgi.FieldStorage()
	machine = form["machine"].value
	benchmark = form["benchmark"].value
	key = form["key"].value

	data = {}
	where = { 'subdir' : benchmark, 'machine' : machine }
	for test in frontend.test.select(db, where):
		if test.iterations.has_key(key):
			data[test.kernel.printable] = test.iterations[key]

	# for kernel in sort_kernels(data.keys()):
	#	print "%s %s" % (kernel, str(data[kernel]))
	title = "%s on %s" % (benchmark, machine)
	graph = plotgraph.gnuplot(title, 'Kernel', key, xsort = sort_kernels)
	graph.add_dataset('all kernels', data)
	graph.plot(cgi_header = True)


def sort_kernels(kernels):
	return sorted(kernels, key = kernel_versions.version_encode)


def draw_graph(title, xlabel, ylabel):
	graph = plotgraph.gnuplot(title, xlabel, ylabel)
	graph.set_xlabels(["2.6.0", "2.6.1", "2.6.2"])
	graph.add_dataset('foo', ["10 0.5", "11 1", "12 2"])
	graph.add_dataset('bar', ["13 0.5", "10 0.2", "9 0.1"])
	graph.plot(cgi_header = True)


main()
