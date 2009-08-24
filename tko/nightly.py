#  tko/nightly.py  code shared by various tko/*.cgi graphing scripts

import cgi, cgitb
import os, sys
import common
from autotest_lib.tko import db, plotgraph, perf
from autotest_lib.client.common_lib import kernel_versions


def add_kernel_jobs(label_pattern):
    cmd = "select job_idx from jobs where label like '%s'" % label_pattern
    nrows = perf.db_cur.execute(cmd)
    return [row[0] for row in perf.db_cur.fetchall()]


def is_filtered_platform(platform, platforms_filter):
    if not platforms_filter:
        return True
    for p in platforms_filter:
        if platform.startswith(p):
            return True
    return False


def get_test_attributes(testrunx):
    cmd = ( "select attribute, value from test_attributes"
            " where test_idx = %d" % testrunx )
    nrows = perf.db_cur.execute(cmd)
    return dict(perf.db_cur.fetchall())


def get_antag(testrunx):
    attrs = get_test_attributes(testrunx)
    return attrs.get('antag', None)


def matching_test_attributes(attrs, required_test_attributes):
    if not required_test_attributes:
        return True
    matches = [attrs[key] == required_test_attributes[key]
               for key in attrs if key in required_test_attributes]
    return min(matches+[True])  # True if all jointly-existing keys matched


def collect_testruns(jobs, test, test_attributes,
                         platforms_filter, by_hosts, no_antag):
    # get test_runs run #s for 1 test on 1 kernel and some platforms
    # TODO: Is jobs list short enough to use directly in 1 sql cmd?
    # TODO: add filtering on test series?
    runs = {}   # platform --> list of test runs
    for jobx in jobs:
        cmd = ( "select test_idx, machine_idx from  tests"
                " where job_idx = %s and test = %s" )
        args = [jobx, test]
        nrows = perf.db_cur.execute(cmd, args)
        for testrunx, machx in perf.db_cur.fetchall():
            platform, host = perf.machine_idx_to_platform_host(machx)
            if by_hosts:
                platform += '.'+host
            if ( is_filtered_platform(platform, platforms_filter)  and
                 matching_test_attributes(get_test_attributes(testrunx),
                                          test_attributes) and
                 (not no_antag or get_antag(testrunx) == '') ):
                runs.setdefault(platform, []).append(testrunx)
    return runs


def all_tested_platforms(test_runs):
    # extract list of all tested platforms from test_runs table
    platforms = set()
    for kernel in test_runs:
        platforms.update(set(test_runs[kernel].keys()))
    return sorted(platforms)


def divide_twoway_testruns(test_runs, platform):
    # partition all twoway runs based on name of antagonist progs
    twoway_runs = {}
    antagonists = set()
    for kernel in test_runs:
        runs = {}
        for testrunx in test_runs[kernel].get(platform, []):
            antag = get_antag(testrunx)
            if antag is not None:
                runs.setdefault(antag, []).append(testrunx)
                antagonists.add(antag)
        twoway_runs[kernel] = runs
    return twoway_runs, sorted(antagonists)


def collect_raw_scores(runs, metric):
    # get unscaled scores of test runs for 1 test on certain jobs
    #   arrange them by platform type
    platform_scores = {}  # platform --> list of perf scores
    for platform in runs:
        vals = perf.get_metric_at_point(runs[platform], metric)
        if vals:
            platform_scores[platform] = vals
    return platform_scores


def collect_scaled_scores(metric, test_runs, regressed_platforms, relative):
    # get scores of test runs for 1 test on some kernels and platforms
    # optionally make relative to oldest (?) kernel on that platform
    # arrange by plotline (ie platform) for gnuplot
    plot_data = {}  # platform --> (kernel --> list of perf scores)
    baseline = {}
    for kernel in sorted(test_runs.keys()):
        for platform in test_runs[kernel]:
            if not (regressed_platforms is None or
                    platform in regressed_platforms):
                continue  # delete results for uninteresting platforms
            vals = perf.get_metric_at_point(test_runs[kernel][platform],
                                            metric)
            if vals:
                if relative:
                    if platform not in baseline:
                        baseline[platform], std = plotgraph.avg_dev(vals)
                    vals = [v/baseline[platform] for v in vals]
                pdp = plot_data.setdefault(platform, {})
                pdp.setdefault(kernel, []).extend(vals)
    return plot_data


def collect_twoway_scores(metric, antagonists, twoway_runs, relative):
    alone = ''
    plot_data = {}
    for kernel in twoway_runs:
        for test2 in antagonists:
            runs = twoway_runs[kernel].get(test2, [])
            vals = perf.get_metric_at_point(runs, metric)
            plot_data.setdefault(test2, {})
            if vals:
                plot_data[test2][kernel] = vals
        if relative:
            vals = plot_data[alone].get(kernel, [])
            if vals:
                baseline = perf.average(vals)
                for test2 in antagonists:
                    vals = plot_data[test2].get(kernel, [])
                    vals = [val/baseline for val in vals]
                    if vals:
                        plot_data[test2][kernel] = vals
            else:
                for test2 in antagonists:
                    if kernel in plot_data[test2]:
                        del plot_data[test2][kernel]
    return plot_data


def find_regressions(kernels, test_runs, metric):
    # A test is regressed on some platform if its latest results are
    #  definitely lower than on the reference kernel.
    # Runs for the latest kernel may be underway and incomplete.
    # In that case, selectively use next-latest kernel.
    # TODO: the next-latest method hurts if latest run is not sorted last,
    #       or if there are several dev threads
    ref    = kernels[0]
    latest = kernels[-1]
    prev   = kernels[-2:][0]
    scores = {}  #  kernel --> (platform --> list of perf scores)
    for k in [ref, prev, latest]:
        if k in test_runs:
            scores[k] = collect_raw_scores(test_runs[k], metric)
    regressed_platforms = []
    for platform in scores[ref]:
        if latest in scores and platform in scores[latest]:
            k = latest
        elif prev in scores and platform in scores[prev]:
            k = prev
        else:  # perhaps due to decay of test machines
            k = ref  # no regression info avail
        ref_avg, ref_std = plotgraph.avg_dev(scores[ref][platform])
        avg,     std     = plotgraph.avg_dev(scores[ k ][platform])
        if avg+std < ref_avg-ref_std:
            regressed_platforms.append(platform)
    return sorted(regressed_platforms)


def get_testrun_context(testrun):
    cmd = ( 'select jobs.label, jobs.tag, tests.subdir,'
            ' tests.started_time'
            ' from jobs, tests'
            ' where jobs.job_idx = tests.job_idx'
            ' and tests.test_idx = %d' % testrun )
    nrows = perf.db_cur.execute(cmd)
    assert nrows == 1
    row = perf.db_cur.fetchone()
    row = [row[0], row[1], row[2], row[3].strftime('%m/%d/%y %H:%M')]
    return row


def html_top():
    print "Content-Type: text/html\n\n<html><body>"


def abs_rel_link(myurl, passthru):
    # link redraws current page with opposite absolute/relative choice
    mod_passthru = passthru[:]
    if 'absolute' in passthru:
        mod_passthru.remove('absolute')
        opposite = 'relative'
    else:
        mod_passthru.append('absolute')
        opposite = 'absolute'
    url = '%s?%s' % (myurl, '&'.join(mod_passthru))
    return "<a href='%s'> %s </a>" % (url, opposite)


def table_1_metric_all_kernels(plot_data, columns, column_argname,
                               kernels, kernel_dates,
                               myurl, filtered_passthru):
    # generate html table of graph's numbers
    #   for 1 benchmark metric over all kernels (rows),
    #   over various platforms or various antagonists etc (cols).
    ref_thresholds = {}
    print "<table border=1 cellpadding=3 cellspacing=0>"
    print "<tr> <td><b> Kernel </b></td>",
    for label in columns:
        if not label and column_argname == 'antag':
            label = 'no antag'
        print "<td><b>", label.replace('_', '<br>_'), "</b></td>"
    print "</tr>"
    for kernel in kernels:
        print "<tr> <td><b>", kernel, "</b>",
        if kernel in kernel_dates:
            print "<br><small>", kernel_dates[kernel], "</small>"
        print "</td>"
        for col in columns:
            print "<td",
            vals = plot_data[col].get(kernel, [])
            if not vals:
                print "> ?",
            else:
                (avg, std_dev) = plotgraph.avg_dev(vals)
                if col not in ref_thresholds:
                    ref_thresholds[col] = avg - std_dev
                if avg+std_dev < ref_thresholds[col]:
                    print "bgcolor=pink",
                print "> ",
                args = filtered_passthru[:]
                perf.append_cgi_args(args,
                   {column_argname:col, 'kernel':kernel})
                print "<a href='%s?%s&runs&attrs'>" % (myurl,
                                                       '&'.join(args))
                print "<b>%.4g</b>" % avg, "</a><br>",
                print "&nbsp; <small> %dr   </small>" % len(vals),
                print "&nbsp; <small> %.3g </small>" % std_dev,
            print "</td>"
        print "</tr>\n"
    print "</table>"
    print "<p> <b>Bold value:</b> Average of this metric, then <br>"
    print "number of good test runs, then standard deviation of those runs"
    print "<br> Pink if regressed from reference kernel"


def table_all_metrics_1_platform(test_runs, platform, relative):
    # TODO: show std dev in cells
    #       can't mark regressions, since some metrics improve downwards
    kernels = perf.sort_kernels(test_runs.keys())
    scores = {}
    attrs = set()
    for kernel in kernels:
        testruns = test_runs[kernel].get(platform, [])
        if testruns:
            d = perf.collect_all_metrics_scores(testruns)
            scores[kernel] = d
            attrs.update(set(d.keys()))
        else:
            print "No runs completed on", kernel, "<br>"
    attrs = sorted(list(attrs))[:100]

    print "<table border=1 cellpadding=4 cellspacing=0>"
    print "<tr><td> Metric </td>"
    for kernel in kernels:
        kernel = kernel.replace("_", "_<br>")
        print "<td>", kernel, "</td>"
    print "</tr>"
    for attr in attrs:
        print "<tr>"
        print "<td>", attr, "</td>"
        baseline = None
        for kernel in kernels:
            print "<td>",
            if kernel in scores and attr in scores[kernel]:
                (avg, dev) = plotgraph.avg_dev(scores[kernel][attr])
                if baseline and relative:
                    percent = (avg/baseline - 1)*100
                    print "%+.1f%%" % percent,
                else:
                    baseline = avg
                    print "%.4g" % avg,
            else:
                print "?"
            print "</td>"
        print "</tr>"
    print "</table>"


def table_variants_all_tests(plot_data, columns, colkeys, benchmarks,
                             myurl, filtered_passthru):
    # generate html table of graph's numbers
    #   for primary metric over all benchmarks (rows),
    #   on one platform and one kernel,
    #   over various combos of test run attribute constraints (cols).
    ref_thresholds = {}
    print "<table border=1 cellpadding=3 cellspacing=0>"
    print "<tr> <td><b> Benchmark </b></td>",
    for col in columns:
        print "<td><b>", colkeys[col].replace(',', ',<br>'), "</b></td>"
    print "</tr>"
    for benchmark in benchmarks:
        print "<tr> <td><b>", benchmark, "</b></td>"
        for col in columns:
            print "<td>",
            vals = plot_data[col].get(benchmark, [])
            if not vals:
                print "?",
            else:
                (avg, std_dev) = plotgraph.avg_dev(vals)
                args = filtered_passthru[:]
                perf.append_cgi_args(args, {'test':benchmark})
                for keyval in colkeys[col].split(','):
                    key, val = keyval.split('=', 1)
                    perf.append_cgi_args(args, {key:val})
                print "<a href='%s?%s&runs&attrs'>" % (myurl,
                                                       '&'.join(args))
                print "<b>%.4g</b>" % avg, "</a><br>",
                print "&nbsp; <small> %dr   </small>" % len(vals),
                print "&nbsp; <small> %.3g </small>" % std_dev,
            print "</td>"
        print "</tr>\n"
    print "</table>"
    print "<p> <b>Bold value:</b> Average of this metric, then <br>"
    print "number of good test runs, then standard deviation of those runs"


def table_testrun_details(runs, metric, tko_server, show_attrs):
    print "<table border=1 cellpadding=4 cellspacing=0>"
    print "<tr><td> %s metric </td>" % metric
    print "<td> Job label </td> <td> Job tag </td> <td> Run results </td>"
    print "<td> Started_time </td>"
    if show_attrs:
        print "<td> Test attributes </td>"
    print "</tr>\n"

    for testrunx in runs:
        print "<tr> <td>",
        vals = perf.get_metric_at_point([testrunx], metric)
        for v in vals:
            print "%.4g&nbsp;" % v,
        print "</td>"
        row = get_testrun_context(testrunx)
        row[2] = ( "<a href='//%s/results/%s/%s/results/keyval'> %s </a>"
                   % (tko_server, row[1], row[2], row[2]) )
        for v in row:
            print "<td> %s </td>" % v
        if show_attrs:
            attrs = get_test_attributes(testrunx)
            print "<td>",
            for attr in sorted(attrs.keys()):
                if attr == "sysinfo-cmdline": continue
                if attr[:4] == "svs-": continue
                val = attrs[attr]
                if len(val) > 40:
                    val = val[:40-3] + "..."
                print "%s=%s &nbsp; &nbsp; " % (attr, val)
            print "</td>"
        print "</tr>\n"
    print "</table>"


def overview_thumb(test, metric, myurl, passthru):
    pass_ = passthru + ['test=%s' % test]
    if metric:
        pass_ += ['metric=%s' % metric]
    pass_ = '&'.join(pass_)
    print "<a    href='%s?%s&table'>"             % (myurl, pass_)
    print "  <img src='%s?%s&size=450,500'> </a>" % (myurl, pass_)
    # embedded graphs fit 3 across on 1400x1050 laptop


def graph_1_test(title, metric, plot_data, line_argname, lines,
                 kernel_legend, relative, size, dark=False):
    # generate graph image for one benchmark, showing avg and
    #  std dev of one metric, over various kernels (X columns),
    #  over various platforms or antagonists etc (graphed lines)
    xlegend = kernel_legend
    ylegend = metric.capitalize()
    if relative:
        ylegend += ', Relative'
        ymin = 0.8
    else:
        ymin = None
    if len(lines) > 1:
        keytitle = line_argname.capitalize() + ':'
    else:
        keytitle = ''
    graph = plotgraph.gnuplot(title, xlegend, ylegend, size=size,
                              xsort=perf.sort_kernels, keytitle=keytitle)
    for line in lines:
        label = line
        if not label and line_argname == 'antag':
            label = 'no antag'
        graph.add_dataset(label, plot_data[line])
    graph.plot(cgi_header=True, ymin=ymin, dark=dark)


def graph_variants_all_tests(title, plot_data, linekeys, size, dark):
        # generate graph image showing all benchmarks
        #   on one platform and one kernel,
        #   over various combos of test run attribute constraints (lines).
    xlegend = "Benchmark"
    ylegend = "Relative Perf"
    graph = plotgraph.gnuplot(title, xlegend, ylegend, size=size)
    for i in linekeys:
        graph.add_dataset(linekeys[i], plot_data[i])
    graph.plot(cgi_header=True, dark=dark, ymin=0.8)


class generate_views(object):


    def __init__(self, kernel_legend, benchmarks, test_group,
                     site_benchmark_metrics, tko_server,
                     jobs_selector, no_antag):
        self.kernel_legend = kernel_legend
        self.benchmarks = benchmarks
        self.test_group = test_group
        self.tko_server = tko_server
        self.jobs_selector = jobs_selector
        self.no_antag = no_antag

        cgitb.enable()
        test, antagonists = self.parse_most_cgi_args()

        perf.init(tko_server=tko_server)
        for b in site_benchmark_metrics:
            perf.add_benchmark_main_metric(b, site_benchmark_metrics[b])

        self.test_runs = {}     # kernel --> (platform --> list of test runs)
        self.job_table = {}     # kernel id --> list of job idxs
        self.kernel_dates = {}  # kernel id --> date of nightly test

        vary = self.cgiform.getlist('vary')
        if vary:
            platform = self.platforms_filter[0]
            self.analyze_variants_all_tests_1_platform(platform, vary)
        elif test:
            self.analyze_1_test(test, antagonists)
        else:
            self.overview_page_all_tests(self.benchmarks, antagonists)


    def collect_all_testruns(self, trimmed_kernels, test):
    # get test_runs run #s for 1 test on some kernels and platforms
        for kernel in trimmed_kernels:
            runs = collect_testruns(self.job_table[kernel], test,
                                    self.test_attributes, self.platforms_filter,
                                    'by_hosts' in self.toggles, self.no_antag)
            if runs:
                self.test_runs[kernel] = runs


    def table_for_graph_1_test(self, title, metric, plot_data,
                                 column_argname, columns, filtered_passthru):
        # generate detailed html page with 1 graph and corresp numbers
        #   for 1 benchmark metric over all kernels (rows),
        #   over various platforms or various antagonists etc (cols).
        html_top()
        print '<h3> %s </h3>' % title
        print ('%s, machine group %s on //%s server <br>' %
               (self.kernel_legend, self.test_group, self.tko_server))
        if self.test_tag:
            print '%s test script series <br>' % self.test_tag[1:]

        print "<img src='%s?%s'>" % (self.myurl, '&'.join(self.passthru))

        link = abs_rel_link(self.myurl, self.passthru+['table'])
        print "<p><p> <h4> Redraw this with %s performance? </h4>" % link

        heading = "%s, %s metric" % (title, metric)
        if self.relative:
            heading += ", relative"
        print "<p><p> <h3> %s: </h3>" % heading
        table_1_metric_all_kernels(plot_data, columns, column_argname,
                                   self.kernels, self.kernel_dates,
                                   self.myurl, filtered_passthru)
        print "</body></html>"


    def graph_1_test_all_platforms(self, test, metric, platforms, plot_data):
        # generate graph image for one benchmark
        title = test.capitalize()
        if 'regress' in self.toggles:
            title += ' Regressions'
        if 'table' in self.cgiform:
            self.table_for_graph_1_test(title, metric, plot_data,
                                        'platforms', platforms,
                                        filtered_passthru=self.passthru)
        else:
            graph_1_test(title, metric, plot_data, 'platforms', platforms,
                         self.kernel_legend, self.relative,
                         self.size, 'dark' in self.toggles)


    def testrun_details(self, title, runs, metric):
        html_top()
        print '<h3> %s </h3>' % title
        print ('%s, machine group %s on //%s server' %
               (self.kernel_legend, self.test_group, self.tko_server))
        if self.test_tag:
            print '<br> %s test script series' % self.test_tag[1:]
        print '<p>'
        table_testrun_details(runs, metric,
                              self.tko_server, 'attrs' in self.cgiform)
        print "</body></html>"


    def testrun_details_for_1_test_kernel_platform(self, test,
                                                   metric, platform):
        default_kernel = min(self.test_runs.keys())
        kernel = self.cgiform.getvalue('kernel', default_kernel)
        title = '%s on %s using %s' % (test.capitalize(), platform, kernel)
        runs = self.test_runs[kernel].get(platform, [])
        self.testrun_details(title, runs, metric)


    def analyze_1_metric_all_platforms(self, test, metric):
        if 'regress' in self.toggles:
            regressed_platforms = find_regressions(self.kernels, self.test_runs,
                                                   metric)
        else:
            regressed_platforms = None
        plot_data = collect_scaled_scores(metric, self.test_runs,
                                          regressed_platforms, self.relative)
        platforms = sorted(plot_data.keys())
        if not plot_data:
            html_top()
            print 'No runs'
        elif 'runs' in self.cgiform:
            self.testrun_details_for_1_test_kernel_platform(test, metric,
                                                            platforms[0])
        else:
            self.graph_1_test_all_platforms(test, metric, platforms, plot_data)


    def analyze_all_metrics_1_platform(self, test, platform):
        # TODO: show #runs in header
        html_top()
        heading = "%s %s:&nbsp %s" % (self.test_group, self.kernel_legend,
                                      test.capitalize())
        print "<h2> %s </h2>" % heading
        print "platform=%s <br>" % platform
        for attr in self.test_attributes:
            print "%s=%s &nbsp; " % (attr, self.test_attributes[attr])
        print "<p>"
        table_all_metrics_1_platform(self.test_runs, platform, self.relative)
        print "</body></html>"


    def table_for_variants_all_tests(self, title, plot_data, colkeys, columns,
                                       filtered_passthru, test_tag):
        # generate detailed html page with 1 graph and corresp numbers
        #   for primary metric over all benchmarks (rows),
        #   on one platform and one kernel,
        #   over various combos of test run attribute constraints (cols).
        html_top()
        print '<h3> %s </h3>' % title
        print ('%s, machine group %s on //%s server <br>' %
               (self.kernel_legend, self.test_group, self.tko_server))
        if test_tag:
            print '%s test script series <br>' % test_tag[1:]

        varies = ['vary='+colkeys[col] for col in columns]
        print "<img src='%s?%s'>" % (self.myurl, '&'.join(self.passthru+varies))

        print "<p><p> <h3> %s: </h3>" % title
        table_variants_all_tests(plot_data, columns, colkeys, self.benchmarks,
                                 self.myurl, filtered_passthru)
        print "</body></html>"


    def analyze_variants_all_tests_1_platform(self, platform, vary):
        # generate one graph image for results of all benchmarks
        # on one platform and one kernel, comparing effects of
        # two or more combos of kernel options (test run attributes)
        #   (numa_fake,stale_page,kswapd_merge,sched_idle, etc)
        kernel = self.cgiform.getvalue('kernel', 'some_kernel')
        self.passthru.append('kernel=%s' % kernel)

        # two or more vary_groups, one for each plotted line,
        # each group begins with vary= and ends with next  &
        # each group has comma-separated list of test attribute key=val pairs
        #    eg   vary=keyval1,keyval2&vary=keyval3,keyval4
        vary_groups = [dict(pair.split('=',1) for pair
                            in vary_group.split(','))
                       for vary_group in vary]

        test = self.benchmarks[0]  # pick any test in all jobs
        kernels, test_tag = self.jobs_selector(test, self.job_table,
                                               self.kernel_dates)

        linekeys = {}
        plot_data = {}
        baselines = {}
        for i, vary_group in enumerate(vary_groups):
            group_attributes = self.test_attributes.copy()
            group_attributes.update(vary_group)
            linekey = ','.join('%s=%s' % (attr, vary_group[attr])
                               for attr in vary_group)
            linekeys[i] = linekey
            data = {}
            for benchmark in self.benchmarks:
                metric = perf.benchmark_main_metric(benchmark)
                runs = collect_testruns(self.job_table[kernel],
                                        benchmark+test_tag,
                                        group_attributes,
                                        self.platforms_filter,
                                        'by_hosts' in self.toggles,
                                        self.no_antag)
                vals = []
                for testrunx in runs[platform]:
                    vals += perf.get_metric_at_point([testrunx], metric)
                if vals:
                    if benchmark not in baselines:
                        baselines[benchmark], stddev = plotgraph.avg_dev(vals)
                    vals = [val/baselines[benchmark] for val in vals]
                    data[benchmark] = vals
            plot_data[i] = data

        title  = "%s on %s" % (kernel, platform)
        for attr in self.test_attributes:
            title += ', %s=%s' % (attr, self.test_attributes[attr])
        if 'table' in self.cgiform:
            self.table_for_variants_all_tests(title, plot_data, linekeys,
                               range(len(linekeys)),
                               filtered_passthru=self.passthru,
                               test_tag=test_tag)
        else:
            graph_variants_all_tests(title, plot_data, linekeys,
                                     self.size, 'dark' in self.toggles)


    def graph_twoway_antagonists_1_test_1_platform(
                  self, test, metric, platform, antagonists, twoway_runs):
        # generate graph of one benchmark's performance paired with
        #    various antagonists, with one plotted line per antagonist,
        #    over most kernels (X axis), all on one machine type
        # performance is relative to the no-antag baseline case
        plot_data = collect_twoway_scores(metric, antagonists,
                                          twoway_runs, self.relative)
        title  = "%s vs. an Antagonist on %s:" % (test.capitalize(), platform)
        if 'table' in self.cgiform:
            filtered_passthru = [arg for arg in self.passthru
                                     if not arg.startswith('antag=')]
            self.table_for_graph_1_test(title, metric, plot_data,
                                   'antag', antagonists,
                                   filtered_passthru=filtered_passthru)
        else:
            graph_1_test(title, metric, plot_data, 'antag', antagonists,
                         self.kernel_legend, self.relative,
                         self.size, 'dark' in self.toggles)


    def testrun_details_for_twoway_test(self, test, metric, platform,
                                        antagonist, twoway_runs):
        default_kernel = min(twoway_runs.keys())
        kernel = self.cgiform.getvalue('kernel', default_kernel)
        title = '%s vs. Antagonist %s on %s using %s' % (
                test.capitalize(), antagonist.capitalize(), platform, kernel)
        runs = twoway_runs[kernel].get(antagonist, [])
        self.testrun_details(title, runs, metric)


    def analyze_twoway_antagonists_1_test_1_platform(
                  self, test, metric, platform, antagonists):
        twoway_runs, all_antagonists = divide_twoway_testruns(self.test_runs,
                                                              platform)
        if antagonists == ['*']:
            antagonists = all_antagonists
        if not twoway_runs:
            html_top()
            print 'No runs'
        elif 'runs' in self.cgiform:
            self.testrun_details_for_twoway_test(
                    test, metric, platform, antagonists[0], twoway_runs)
        else:
            self.graph_twoway_antagonists_1_test_1_platform(
                    test, metric, platform, antagonists, twoway_runs)


    def get_twoway_default_platform(self):
        if self.platforms_filter:
            return self.platforms_filter[0]
        test = 'unixbench'
        kernels, test_tag = self.jobs_selector(test, self.job_table,
                                               self.kernel_dates)
        self.collect_all_testruns(kernels, test+test_tag)
        return all_tested_platforms(self.test_runs)[0]


    def overview_page_all_tests(self, benchmarks, antagonists):
        # generate overview html page with small graphs for each benchmark
        #   linking to detailed html page for that benchmark
        #   recursively link to this same cgi to generate each image
        html_top()
        if antagonists is not None:
            heading = ('Twoway Container Isolation using %s on %s' %
                       (self.kernel_legend, self.get_twoway_default_platform()))
        else:
            heading = '%s, %s Benchmarks' % (self.kernel_legend,
                                             self.test_group)
        if 'regress' in self.toggles:
            heading += ", Regressions Only"
        print "<h3> %s </h3>" % heading
        for test in benchmarks:
            overview_thumb(test, '', self.myurl, self.passthru)
            if test == 'unixbench':
                overview_thumb('unixbench', 'Process_creation',
                               self.myurl, self.passthru)

        link = abs_rel_link(self.myurl, self.passthru)
        print "<p><p> <h4> Redraw this with %s performance? </h4>" % link
        print "</body></html>"


    def analyze_1_test(self, test, antagonists):
        self.passthru.append('test=%s' % test)
        metric = self.cgiform.getvalue('metric', '')
        if metric:
            self.passthru.append('metric=%s' % metric)
        else:
            metric = perf.benchmark_main_metric(test)
            assert metric, "no default metric for test %s" % test
        self.kernels, self.test_tag = self.jobs_selector(test, self.job_table,
                                                         self.kernel_dates)
        self.collect_all_testruns(self.kernels, test+self.test_tag)
        if not self.platforms_filter and (metric == '*' or
                                          antagonists is not None):
            # choose default platform
            self.platforms_filter = all_tested_platforms(self.test_runs)[0:1]
            self.passthru.append('platforms=%s' %
                                 ','.join(self.platforms_filter))
        if antagonists is not None:
            antagonists = antagonists.split(',')
            if len(antagonists) == 1 and antagonists != ['*']:
                self.relative = False
            self.analyze_twoway_antagonists_1_test_1_platform(
                    test, metric, self.platforms_filter[0], antagonists)
        elif metric == '*':
            platform = self.platforms_filter[0]
            self.analyze_all_metrics_1_platform(test, platform)
        else:
            self.analyze_1_metric_all_platforms(test, metric)


    def parse_most_cgi_args(self):
        self.myurl = os.path.basename(sys.argv[0])
        self.cgiform = cgi.FieldStorage(keep_blank_values=True)
        self.size = self.cgiform.getvalue('size', '1200,850')
        all_toggles = set(('absolute', 'regress', 'dark', 'by_hosts'))
        self.toggles = set(tog for tog in all_toggles if tog in self.cgiform)
        platforms = self.cgiform.getvalue('platforms', '')
        if '.' in platforms:
            self.toggles.add('by_hosts')
        self.passthru = list(self.toggles)
        self.relative = 'absolute' not in self.toggles
        if platforms:
            self.passthru.append('platforms=%s' % platforms)
            self.platforms_filter = platforms.split(',')
        else:
            self.platforms_filter = []
        self.test_attributes = perf.parse_test_attr_args(self.cgiform)
        perf.append_cgi_args(self.passthru, self.test_attributes)
        test = self.cgiform.getvalue('test', '')
        if 'antag' in self.cgiform:
            antagonists = ','.join(self.cgiform.getlist('antag'))
            #      antag=*
            #   or antag=test1,test2,test3,...
            #   or antag=test1&antag=test2&...
            #   testN is empty for solo case of no antagonist
            self.passthru.append('antag=%s' % antagonists)
        else:
            antagonists = None  # not same as ''
        return test, antagonists
