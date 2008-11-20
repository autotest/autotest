#!/usr/bin/python
# solo_compare_graph.cgi: generate one graph image for solo container results 
# of all benchmarks on one platform and kernel, comparing effects of two or 
# more combos of kernel options (numa_fake, stale_page, kswapd_merge, sched_idle)

__author__ = """duanes@google.com (Duane Sand), Copyright Google 2008"""

import cgi, cgitb
import common
from autotest_lib.tko import perf, plotgraph


def get_cgi_args():
    cgitb.enable()
    form = cgi.FieldStorage(keep_blank_values=True)

    platform = form.getvalue('platform', '')
    # required  platform=xyz
    #     e.g.  platform=Warp18
    #     graph for selected type of test machines, & variants

    kernel   = form.getvalue('kernel', '')
    # required  kernel=xyz
    #     e.g.  kernel=2.6.18-smp-230.0

    graph_size = form.getvalue('size', '700,450' )
    # optional size=width,height     (in pixels)

    dark = form.has_key('dark')
    # optional, graph uses dark navy background

    common_attrs = perf.parse_test_attr_args(form)
    # optional test attributes shared by all plotted lines
    # see variations listed in perf.py

    vary_attrs = [dict([pair.split('=',1) for pair in vary_group.split(',')])
                  for vary_group in form.getlist('vary')]
    # required, two or more vary-groups, one for each plotted line
    # each group has comma-separated list of test attributes, ended by &
    #     vary=testattr1,testattr2,...
    # each test attribute is keyval pair
    #     attrname=value 
 
    if not vary_attrs:   # for cgi testing convenience
        vary_attrs = [{'numa_fake':'64'}, {'numa_fake':'128M'}]
    if not platform:
        platform  = 'Ilium'       # for cgi testing convenience
    if not kernel:
        kernel    = '2.6.18-smp-230.0_rc11'  # for cgi testing convenience       
    return (platform, kernel, common_attrs, vary_attrs, graph_size, dark)


def one_graph():
    perf.init()
    (platform, kernel, common_attrs, vary_attrs, 
        graph_size, dark) = get_cgi_args()
    kernels = perf.kernels()
    kernel_idx = kernels.kernel_name_to_idx(kernel)
    title  = "%s on %s" % (kernel, platform)
    for attr in common_attrs:
        title += ', %s=%s' % (attr, common_attrs[attr])
    xlegend = "Benchmark, Solo"
    ylegend = "Relative Perf"
    graph = plotgraph.gnuplot(title, xlegend, ylegend, size=graph_size)
    baselines = {}
    for vary in vary_attrs:
        test_attributes = common_attrs.copy()
        linekey = ''
        for attr in vary:
            test_attributes[attr] = vary[attr]
            linekey += '%s=%s ' % (attr, vary[attr])
        twoway = perf.twoway_queries(kernels, selected_platforms=platform,
                                     one_kernel=kernel_idx, 
                                     selected_test_attrs=test_attributes)
        data = {}
        for benchmark in twoway.testnames:
            metric = perf.benchmark_main_metric(benchmark)
            vals = twoway.get_scores(kernel_idx, platform, 
                                     benchmark, '', metric)
            if vals:
                if benchmark not in baselines:
                    baselines[benchmark], stddev = plotgraph.avg_dev(vals)
                vals = [val/baselines[benchmark] for val in vals]
                data[benchmark] = vals
        if data:
            graph.add_dataset(linekey, data)
    graph.plot(cgi_header=True, dark=dark, ymin=0.8)


one_graph()
