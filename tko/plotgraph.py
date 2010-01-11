# Copyright Martin J. Bligh (mbligh@google.com), 2007

"""
Class to draw gnuplot graphs for autotest performance analysis.
Not that generic - specifically designed to to draw graphs of one type,
but probably adaptable.
"""

import subprocess, sys, os
from math import sqrt
Popen = subprocess.Popen

def avg_dev(values):
    if len(values) == 0:
        return (0,0)
    average = float(sum(values)) / len(values)
    sum_sq_dev = sum( [(x - average) ** 2 for x in values] )
    std_dev = sqrt(sum_sq_dev / float(len(values)));
    return (average, std_dev);


class gnuplot:
    def __init__(self, title, xlabel, ylabel, xsort = sorted, size = "1180,900", keytitle = None):
        self.title = title
        self.xlabel = xlabel
        self.ylabel = ylabel
        self.data_titles = []
        self.datasets = []
        self.xsort = xsort
        self.xvalues = set([])
        self.size = size
        self.keytitle = keytitle

    def xtics(self):
        count = 1
        tics = []
        for label in self.xlabels:
            # prepend 2 blanks to work around gnuplot bug
            #  in placing X axis legend over X tic labels
            tics.append('"  %s" %d' % (label, count))
            count += 1
        return tics


    def add_dataset(self, title, labeled_values):
        """
        Add a data line

        title: title of the dataset
        labeled_values: dictionary of lists
                        { label : [value1, value2, ... ] , ... }
        """
        if not labeled_values:
            raise "plotgraph:add_dataset - dataset was empty! %s" %\
                                                            title
        self.data_titles.append(title)
        data_points = {}
        for label in labeled_values:
            point = "%s %s" % avg_dev(labeled_values[label])
            data_points[label] = point
            self.xvalues.add(label)
        self.datasets.append(data_points)


    def plot(self, cgi_header = False, output = None, test = None):
        if cgi_header:
            print "Content-type: image/png\n"
            sys.stdout.flush()
        if test:
            g = open(test, 'w')
        else:
            p = Popen("/usr/bin/gnuplot", stdin = subprocess.PIPE)
            g = p.stdin
        g.write('set terminal png size %s\n' % self.size)
        if self.keytitle:
            g.write('set key title "%s"\n' % self.keytitle)
            g.write('set key outside\n')  # outside right
        else:
            g.write('set key below\n')
        g.write('set title "%s"\n' % self.title)
        g.write('set xlabel "%s"\n' % self.xlabel)
        g.write('set ylabel "%s"\n' % self.ylabel)
        if output:
            g.write('set output "%s"\n' % output)
        g.write('set style data yerrorlines\n')
        g.write('set grid\n')

        self.xlabels = self.xsort(list(self.xvalues))

        g.write('set xrange [0.5:%f]\n' % (len(self.xvalues)+0.5))
        g.write('set xtics rotate (%s)\n' % ','.join(self.xtics()))

        plot_lines = ['"-" title "%s"' % t for t in self.data_titles]
        g.write('plot ' + ', '.join(plot_lines) + '\n')

        for dataset in self.datasets:
            count = 1
            for label in self.xlabels:
                if label in dataset:
                    data = dataset[label]
                    g.write("%d %s\n" % (count, str(data)))
                count += 1
            sys.stdout.flush()
            g.write('e\n')

        g.close()
        if not test:
            sts = os.waitpid(p.pid, 0)
