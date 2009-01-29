#!/usr/bin/python
# perf_graph.cgi: generate image of one graph of a benchmark's performance

__author__ = """duanes@google.com (Duane Sand), Copyright Google 2008"""

import cgi, cgitb
import common
from autotest_lib.tko import perf, plotgraph


def get_cgi_args():
    cgitb.enable()
    form = cgi.FieldStorage(keep_blank_values=True)

    benchmark  = form.getvalue('test',   '')
    # required  test=testname          (untagged runs only) 
    #       or  test=testname.sometags
    #       or  test=testname*         (combines all tags except .twoway)
    #       or  test=testname.twoway*  (combines twoway tags)
    #     e.g.  test=dbench

    metric     = form.getvalue('metric', '')
    # optional  metric=attributename   (from testname.tag/results/keyval)
    #       or  metric=1/attributename
    #       or  metric=geo_mean        (combines all attributes)
    #       or  metric=good_testrun_count   (tally of runs)
    #       or  metric=$testattrname   (from testname.tag/keyval)
    #     e.g.  metric=throughput
    #           metric=$stale_page_age
    #           metric=$version        (show test's version #)
    #     defaults to test's main performance attribute, if known   

    one_user   = form.getvalue('user',   '')
    # optional  user=linuxuserid    
    #     restrict results just to testrun jobs submitted by that user
    #     defaults to all users

    selected_platforms = form.getvalue('platforms', '')
    # optional  platforms=plat1,plat2,plat3...
    #     where platN is  xyz       (combines all xyz_variants as one plotline)
    #                 or  xyz$      (plots each xyz_variant separately)
    #     restrict results just to selected types of test machines
    #     defaults to commonly used types, combining variants 

    selected_machines  = form.getvalue('machines',  '')
    # optional  machines=mname1,mname2,mname3...
    #       or  machines=mnam*       (single set of similar host names)
    #       or  machines=yings       (abbrev for ying's benchmarking machines)
    #     where mnameN is network hostname of a test machine, eg bdcz12
    #     restricts results just to selected test machines
    #     defaults to all machines of selected platform types
    
    graph_size = form.getvalue('size', '640,500' )
    # optional size=width,height     (in pixels)

    dark = form.has_key('dark')

    test_attributes = perf.parse_test_attr_args(form)
    #  see variations listed in perf.py

    if not benchmark:
        benchmark = 'dbench*'      # for cgi testing convenience
    if not metric:
        # strip tags .eth0  etc and * wildcard from benchmark name
        bname = benchmark.split('.',1)[0].rstrip('*')
        metric = perf.benchmark_main_metric(bname)
        assert metric, "no default metric for test %s" % bname
    return (benchmark, metric, selected_platforms, 
            selected_machines, one_user, graph_size, dark, test_attributes)


def one_performance_graph():
    # generate image of graph of one benchmark's performance over
    #    most kernels (X axis) and all machines (one plotted line per type)
    perf.init()
    (benchmark, metric, selected_platforms, selected_machines,
        one_user, graph_size, dark, test_attributes) = get_cgi_args()
    kernels = perf.kernels()
    kernels.get_all_kernel_names()
    machine_to_platform, platforms_order = perf.get_platform_info(
                                selected_platforms, selected_machines)
    selected_jobs = perf.select_jobs(one_user, machine_to_platform)
    possible_tests = perf.identify_relevent_tests(
                                benchmark, selected_jobs, 
                                kernels, machine_to_platform)
    data = perf.collect_test_results(possible_tests, kernels, 
                                     metric, test_attributes)
    title = benchmark.capitalize() + " Performance"
    graph = plotgraph.gnuplot(title, 'Kernels', metric.capitalize(), 
                              xsort=perf.sort_kernels, size=graph_size)
    for platform in platforms_order:
        if platform in data:
            graph.add_dataset(platform, data[platform])
    graph.plot(cgi_header=True, dark=dark)


one_performance_graph()
