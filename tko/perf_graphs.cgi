#!/usr/bin/python
# perf_graphs.cgi: generate web page showing multiple graphs of benchmarks' performance

import cgi, cgitb
import common
from autotest_lib.tko import perf


def multiple_graphs_page(benchmarks):
    # Generate html for web page showing graphs for all benchmarks
    # Each graph image is formed by an invocation of 2nd cgi file
    print "Content-Type: text/html\n"
    print "<html><body bgcolor='#001c38' text='#b0d8f0'>"
    print "<h3><center> Kernel Benchmarks",
    if one_user:
        print "By User", one_user,
    if machine_names:
        print "On Selected",
    else:
        print "On All ",
    print "Machines </center></h3>"

    for bench in benchmarks:
        args = ['test=%s*' % bench, 'dark']
        if one_user:
            args.append('user=%s' % one_user)
        if graph_size:
            args.append('size=%s' % graph_size)
        if platforms:
            args.append('platforms=%s' % platforms)
        if machine_names:
            args.append('machines=%s' % machine_names)
        perf.append_cgi_args(args, test_attributes)
        print "<img src='perf_graph.cgi?%s'" % '&'.join(args),
        print " vspace=5 hspace=5>"

    if one_user != 'yinghan':
        print "<p> Uncontrolled results!"
        print "Not using just the controlled benchmarking machines."
        print "Variants of a platform type (mem size, # disks, etc) may be"
        print "lumped together."
        print "Non-default test args may have been applied in some cases."
        print "No-container cases and whole-machine single-container cases"
        print "are lumped together."
    print "</body></html>"


cgitb.enable()
form = cgi.FieldStorage()
platforms     = form.getvalue('platforms', '')
machine_names = form.getvalue('machines',  '')
one_user      = form.getvalue('user',      '')
graph_size    = form.getvalue('size',      '')
test_attributes = perf.parse_test_attr_args(form)
# see perf_graph.cgi for these options
if machine_names == 'yings' and not one_user:
    one_user = 'yinghan'
    benchmarks = ['dbench', 'iozone', 'kernbench', 'tbench', 'unixbench']
    if not graph_size:
        graph_size = '400,345'
else:
    benchmarks = perf.usual_benchmarks
multiple_graphs_page(benchmarks)
