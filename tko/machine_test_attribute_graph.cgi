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
#	form = cgi.FieldStorage()
#	if not form.has_key("machine") and form.has_key("kernel"):
#		raise
#
#	machine = form["machine"].value
#	kernel_version = form["kernel"].value
#	draw_graph("A test graph", "Kernel", "Elapsed time (seconds)")
	print "Content-type: text/html\n"
	sys.stdout.flush()
	machine = 'cagg4'
	where = { 'subdir' : 'kernbench', 'machine' : machine }
	tests = frontend.test.select(db, where)
	kernels.sort(key = kernel_encode)



def draw_graph(title, xlabel, ylabel):
	graph = plotgraph.gnuplot(title, xlabel, ylabel)
	graph.set_xlabels(["2.6.0", "2.6.1", "2.6.2"])
	graph.add_dataset('foo', ["10 0.5", "11 1", "12 2"])
	graph.add_dataset('bar', ["13 0.5", "10 0.2", "9 0.1"])
	graph.plot(cgi_header = True)


main()
