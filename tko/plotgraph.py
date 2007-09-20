# Copyright Martin J. Bligh (mbligh@google.com), 2007

"""
Class to draw gnuplot graphs for autotest performance analysis.
Not that generic - specifically designed to to draw graphs of one type,
but probably adaptable.
"""

import subprocess, sys, os
Popen = subprocess.Popen

class gnuplot:
	def __init__(self, title, xlabel, ylabel):
		self.title = title
		self.xlabel = xlabel
		self.ylabel = ylabel
		self.data_titles = []
		self.datasets = []


	def set_xlabels(self, labels):
		count = 1
		self.xtics = []
		for label in labels:
			self.xtics.append('"%s" %d' % (label, count))
			count += 1


	def add_dataset(self, title, values):
		"""
		Add a data line

		For yerrorbars, values should be "<value> <error>" as a string
		"""
		self.data_titles.append(title)
		self.datasets.append(values)


	def plot(self, cgi_header = False, output = None, test = None):
		if cgi_header:
			print "Content-type: image/png\n"
			sys.stdout.flush()
		if test:
			g = open(test, 'w')
		else:
			p = Popen("/usr/bin/gnuplot", stdin = subprocess.PIPE)
			g = p.stdin
		g.write('set terminal png size 1380,900\n')
		g.write('set key below\n')
		g.write('set title "%s"\n' % self.title)
		g.write('set xlabel "%s"\n' % self.xlabel)
		g.write('set ylabel "%s"\n' % self.ylabel)
		if output:
			g.write('set output "%s"\n' % output)
		g.write('set style data yerrorlines\n')
		g.write('set grid\n')

		g.write('set xtics rotate (%s)\n' % ','.join(self.xtics))

		plot_lines = ['"-" title "%s"' % t for t in self.data_titles]
		g.write('plot ' + ', '.join(plot_lines) + '\n')

		for dataset in self.datasets:
			count = 1
			for data in dataset:
				g.write("%d %s\n" % (count, str(data)))
				count += 1
			g.write('e\n')

		g.close()
		if not test:
			sts = os.waitpid(p.pid, 0)

