#!/usr/bin/python

# http://test.kernel.org/perf/kernbench.elm3b6.png

import cgi, cgitb, os, sys, re, subprocess
cgitb.enable()
Popen = subprocess.Popen

import common
from autotest_lib.tko import db, display, frontend, plotgraph
from autotest_lib.client.common_lib import kernel_versions

released_kernel = re.compile('2\.\d\.\d+(-smp-)[0-9]{3}\.[0-9]$')
rc_kernel = re.compile('2\.\d\.\d+(-smp-)[0-9]{3}\.[0-9]_rc[0-9]$')
db = db.db()

def main():
    form = cgi.FieldStorage()

    if form.has_key("benchmark_key"):
        benchmark_key = form["benchmark_key"].value
        # input is a list of benchmark:key values -- benchmark1:key1,...
        # this loop separates this out into two lists
        benchmark_idx = []
        key_idx = []
        for benchmark_key_pair in benchmark_key.split(','):
            (benchmark, key) = benchmark_key_pair.split(':')
            benchmark_idx.append(benchmark)
            key_idx.append(key)
    elif form.has_key("benchmark") and form.has_key("key"):
        benchmarks = form["benchmark"].value
        keys = form["key"].value

        benchmark_idx = benchmarks.split(',')
        key_idx = keys.split(',')
    else:
        # Ignore this for by setting benchmark_idx and key_idx to be
        # empty lists.
        benchmark_idx = []
        key_idx = []

    machine_idx = form["machine"].value
    kernel = form["kernel"].value
    if kernel == "released":
        kernel = released_kernel    
    if kernel == "rc":
        kernel = rc_kernel

    machine = frontend.machine.select(db, {'hostname' : machine_idx})[0]

    #get the machine type from machinename
    for line in open('machines', 'r'):
        words = line.rstrip().split('\t')
        if words[0] == machine.hostname:
            title = '%s (%s)' % (words[-1], machine.hostname)
        else:
            title = '%s' % machine.hostname

    graph = plotgraph.gnuplot(title, 'Kernel', 'normalized throughput (%)', xsort = sort_kernels, size = "600,500")
    for benchmark, key in zip(benchmark_idx, key_idx):
        reference_value = None
        data = {}
        where = { 'subdir' : benchmark, 'machine_idx' : machine.idx , 'status' : 6}

        #select the corresponding kernels and sort by the release version
        kernels = set([])
        kernels_sort = set([])
        kernels_idx = set([])
        for test in frontend.test.select(db, where):
            if kernel == "all":
                kernels.add(test.kernel().printable)
                kernels_idx.add(str(test.kernel().idx))

            elif kernel == "experimental":
                if not re.match(released_kernel, test.kernel().printable)\
                and not re.match(rc_kernel, test.kernel().printable):
                    kernels.add(test.kernel().printable)
                    kernels_idx.add(str(test.kernel().idx))
            else:
                if re.match(kernel, test.kernel().printable):
                    kernels.add(test.kernel().printable)
                    kernels_idx.add(str(test.kernel().idx))
        kernels_sort = sort_kernels(list(kernels))

        #get the base value for each benchmark
        kernel_base = frontend.kernel.select(db, {'printable' : kernels_sort[0]})[0]
        for test in frontend.test.select(db, { 'subdir' : benchmark, 'machine_idx' : machine.idx, 'kernel_idx' : kernel_base.idx}):
            iterations = test.iterations()
            if iterations.has_key(key):
                reference_value = sum(iterations[key])/len(iterations[key])
                break

        wherein = { 'kernel_idx' : kernels_idx }
        for test in frontend.test.select(db, where, wherein):
            iterations = test.iterations()
            if iterations.has_key(key):
                # Maintain a list of every test result in data.
                # Initialize this list, if it does not exist.
                if not data.has_key(test.kernel().printable):
                    data[test.kernel().printable] = list()

                if benchmark == "kernbench":
                    results = [((reference_value / i - 1)*100) for i in iterations[key]]
                else:
                    results = [((i / reference_value - 1)*100) for i in iterations[key]]
                data[test.kernel().printable].extend(results)

        graph.add_dataset(benchmark+' ( '+key+' ) ',data)

    graph.plot(cgi_header = True)


def sort_kernels(kernels):
    return sorted(kernels, key = kernel_versions.version_encode)

main()
