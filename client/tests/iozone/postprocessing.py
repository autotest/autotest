#!/usr/bin/python
"""
Postprocessing module for IOzone. It is capable to pick results from an
IOzone run, calculate the geometric mean for all throughput results for
a given file size or record size, and then generate a series of 2D and 3D
graphs. The graph generation functionality depends on gnuplot, and if it
is not present, functionality degrates gracefully.

@copyright: Red Hat 2010
"""
import os, sys, optparse, logging, math, time
import common
from autotest_lib.client.common_lib import logging_config, logging_manager
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils, os_dep


_LABELS = ['file_size', 'record_size', 'write', 'rewrite', 'read', 'reread',
           'randread', 'randwrite', 'bkwdread', 'recordrewrite', 'strideread',
           'fwrite', 'frewrite', 'fread', 'freread']


def unique(list):
    """
    Return a list of the elements in list, but without duplicates.

    @param list: List with values.
    @return: List with non duplicate elements.
    """
    n = len(list)
    if n == 0:
        return []
    u = {}
    try:
        for x in list:
            u[x] = 1
    except TypeError:
        return None
    else:
        return u.keys()


def geometric_mean(values):
    """
    Evaluates the geometric mean for a list of numeric values.

    @param values: List with values.
    @return: Single value representing the geometric mean for the list values.
    @see: http://en.wikipedia.org/wiki/Geometric_mean
    """
    try:
        values = [int(value) for value in values]
    except ValueError:
        return None
    product = 1
    n = len(values)
    if n == 0:
        return None
    return math.exp(sum([math.log(x) for x in values])/n)


def compare_matrices(matrix1, matrix2, treshold=0.05):
    """
    Compare 2 matrices nxm and return a matrix nxm with comparison data

    @param matrix1: Reference Matrix with numeric data
    @param matrix2: Matrix that will be compared
    @param treshold: Any difference bigger than this percent treshold will be
            reported.
    """
    improvements = 0
    regressions = 0
    same = 0
    comparison_matrix = []

    new_matrix = []
    for line1, line2 in zip(matrix1, matrix2):
        new_line = []
        for element1, element2 in zip(line1, line2):
            ratio = float(element2) / float(element1)
            if ratio < (1 - treshold):
                regressions += 1
                new_line.append((100 * ratio - 1) - 100)
            elif ratio > (1 + treshold):
                improvements += 1
                new_line.append("+" + str((100 * ratio - 1) - 100))
            else:
                same + 1
                if line1.index(element1) == 0:
                    new_line.append(element1)
                else:
                    new_line.append(".")
        new_matrix.append(new_line)

    total = improvements + regressions + same

    return (new_matrix, improvements, regressions, total)


class IOzoneAnalyzer(object):
    """
    Analyze an unprocessed IOzone file, and generate the following types of
    report:

    * Summary of throughput for all file and record sizes combined
    * Summary of throughput for all file sizes
    * Summary of throughput for all record sizes

    If more than one file is provided to the analyzer object, a comparison
    between the two runs is made, searching for regressions in performance.
    """
    def __init__(self, list_files, output_dir):
        self.list_files = list_files
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)
        self.output_dir = output_dir
        logging.info("Results will be stored in %s", output_dir)


    def average_performance(self, results, size=None):
        """
        Flattens a list containing performance results.

        @param results: List of n lists containing data from performance runs.
        @param size: Numerical value of a size (say, file_size) that was used
                to filter the original results list.
        @return: List with 1 list containing average data from the performance
                run.
        """
        average_line = []
        if size is not None:
            average_line.append(size)
        for i in range(2, 15):
            average = geometric_mean([line[i] for line in results]) / 1024.0
            average = int(average)
            average_line.append(average)
        return average_line


    def process_results(self, results, label=None):
        """
        Process a list of IOzone results according to label.

        @label: IOzone column label that we'll use to filter and compute
                geometric mean results, in practical term either 'file_size'
                or 'record_size'.
        @result: A list of n x m columns with original iozone results.
        @return: A list of n-? x (m-1) columns with geometric averages for
                values of each label (ex, average for all file_sizes).
        """
        performance = []
        if label is not None:
            index = _LABELS.index(label)
            sizes = unique([line[index] for line in results])
            sizes.sort()
            for size in sizes:
                r_results = [line for line in results if line[index] == size]
                performance.append(self.average_performance(r_results, size))
        else:
            performance.append(self.average_performance(results))

        return performance


    def parse_file(self, file):
        """
        Parse an IOzone results file.

        @param file: File object that will be parsed.
        @return: Matrix containing IOzone results extracted from the file.
        """
        lines = []
        for line in file.readlines():
            fields = line.split()
            if len(fields) != 15:
                continue
            try:
                lines.append([int(i) for i in fields])
            except ValueError:
                continue
        return lines


    def report(self, overall_results, record_size_results, file_size_results):
        """
        Generates analysis data for IOZone run.

        Generates a report to both logs (where it goes with nice headers) and
        output files for further processing (graph generation).

        @param overall_results: 1x15 Matrix containing IOzone results for all
                file sizes
        @param record_size_results: nx15 Matrix containing IOzone results for
                each record size tested.
        @param file_size_results: nx15 Matrix containing file size results
                for each file size tested.
        """
        # Here we'll use the logging system to put the output of our analysis
        # to files
        logger = logging.getLogger()
        formatter = logging.Formatter("")

        logging.info("")
        logging.info("TABLE:  SUMMARY of ALL FILE and RECORD SIZES                        Results in MB/sec")
        logging.info("")
        logging.info("FILE & RECORD  INIT    RE              RE    RANDOM  RANDOM  BACKWD   RECRE  STRIDE    F       FRE     F       FRE")
        logging.info("SIZES (KB)     WRITE   WRITE   READ    READ    READ   WRITE    READ   WRITE    READ    WRITE   WRITE   READ    READ")
        logging.info("-------------------------------------------------------------------------------------------------------------------")
        for result_line in overall_results:
            logging.info("ALL            %-8s%-8s%-8s%-8s%-8s%-8s%-8s%-8s%-8s%-8s%-8s%-8s%-8s" % tuple(result_line))
        logging.info("")

        logging.info("DRILLED DATA:")

        logging.info("")
        logging.info("TABLE:  RECORD Size against all FILE Sizes                          Results in MB/sec")
        logging.info("")
        logging.info("RECORD    INIT    RE              RE    RANDOM  RANDOM  BACKWD   RECRE  STRIDE    F       FRE     F       FRE ")
        logging.info("SIZE (KB) WRITE   WRITE   READ    READ    READ   WRITE    READ   WRITE    READ    WRITE   WRITE   READ    READ")
        logging.info("--------------------------------------------------------------------------------------------------------------")

        foutput_path = os.path.join(self.output_dir, '2d-datasource-file')
        if os.path.isfile(foutput_path):
            os.unlink(foutput_path)
        foutput = logging.FileHandler(foutput_path)
        foutput.setFormatter(formatter)
        logger.addHandler(foutput)
        for result_line in record_size_results:
            logging.info("%-10s%-8s%-8s%-8s%-8s%-8s%-8s%-8s%-8s%-8s%-8s%-8s%-8s%-8s" % tuple(result_line))
        logger.removeHandler(foutput)

        logging.info("")

        logging.info("")
        logging.info("TABLE:  FILE Size against all RECORD Sizes                          Results in MB/sec")
        logging.info("")
        logging.info("RECORD    INIT    RE              RE    RANDOM  RANDOM  BACKWD   RECRE  STRIDE    F       FRE     F       FRE ")
        logging.info("SIZE (KB) WRITE   WRITE   READ    READ    READ   WRITE    READ   WRITE    READ    WRITE   WRITE   READ    READ")
        logging.info("--------------------------------------------------------------------------------------------------------------")

        routput_path = os.path.join(self.output_dir, '2d-datasource-record')
        if os.path.isfile(routput_path):
            os.unlink(routput_path)
        routput = logging.FileHandler(routput_path)
        routput.setFormatter(formatter)
        logger.addHandler(routput)
        for result_line in file_size_results:
            logging.info("%-10s%-8s%-8s%-8s%-8s%-8s%-8s%-8s%-8s%-8s%-8s%-8s%-8s%-8s" % tuple(result_line))
        logger.removeHandler(routput)

        logging.info("")


    def report_comparison(self, record, file):
        """
        Generates comparison data for 2 IOZone runs.

        It compares 2 sets of nxm results and outputs a table with differences.
        If a difference higher or smaller than 5% is found, a warning is
        triggered.

        @param record: Tuple with 4 elements containing results for record size.
        @param file: Tuple with 4 elements containing results for file size.
        """
        (record_size, record_improvements, record_regressions,
         record_total) = record
        (file_size, file_improvements, file_regressions,
         file_total) = file
        logging.info("ANALYSIS of DRILLED DATA:")

        logging.info("")
        logging.info("TABLE:  RECsize Difference between runs                            Results are % DIFF")
        logging.info("")
        logging.info("RECORD    INIT    RE              RE    RANDOM  RANDOM  BACKWD   RECRE  STRIDE    F       FRE     F       FRE ")
        logging.info("SIZE (KB) WRITE   WRITE   READ    READ    READ   WRITE    READ   WRITE    READ    WRITE   WRITE   READ    READ")
        logging.info("--------------------------------------------------------------------------------------------------------------")
        for result_line in record_size:
            logging.info("%-10s%-8.6s%-8.6s%-8.6s%-8.6s%-8.6s%-8.6s%-8.6s%-8.6s%-8.6s%-8.6s%-8.6s%-8.6s%-8.6s" % tuple(result_line))
        logging.info("REGRESSIONS: %d (%.2f%%)    Improvements: %d (%.2f%%)",
                     record_regressions,
                     (100 * record_regressions/float(record_total)),
                     record_improvements,
                     (100 * record_improvements/float(record_total)))
        logging.info("")

        logging.info("")
        logging.info("TABLE:  FILEsize Difference between runs                           Results are % DIFF")
        logging.info("")
        logging.info("RECORD    INIT    RE              RE    RANDOM  RANDOM  BACKWD   RECRE  STRIDE    F       FRE     F       FRE ")
        logging.info("SIZE (KB) WRITE   WRITE   READ    READ    READ   WRITE    READ   WRITE    READ    WRITE   WRITE   READ    READ")
        logging.info("--------------------------------------------------------------------------------------------------------------")
        for result_line in file_size:
            logging.info("%-10s%-8.6s%-8.6s%-8.6s%-8.6s%-8.6s%-8.6s%-8.6s%-8.6s%-8.6s%-8.6s%-8.6s%-8.6s%-8.6s" % tuple(result_line))
        logging.info("REGRESSIONS: %d (%.2f%%)    Improvements: %d (%.2f%%)",
                     file_regressions,
                     (100 * file_regressions/float(file_total)),
                     file_improvements,
                     (100 * file_improvements/float(file_total)))
        logging.info("")


    def analyze(self):
        """
        Analyzes and eventually compares sets of IOzone data.
        """
        overall = []
        record_size = []
        file_size = []
        for path in self.list_files:
            file = open(path, 'r')
            logging.info('FILE: %s', path)

            results = self.parse_file(file)

            overall_results = self.process_results(results)
            record_size_results = self.process_results(results, 'record_size')
            file_size_results = self.process_results(results, 'file_size')
            self.report(overall_results, record_size_results, file_size_results)

            if len(self.list_files) == 2:
                overall.append(overall_results)
                record_size.append(record_size_results)
                file_size.append(file_size_results)

        if len(self.list_files) == 2:
            record_comparison = compare_matrices(*record_size)
            file_comparison = compare_matrices(*file_size)
            self.report_comparison(record_comparison, file_comparison)


class IOzonePlotter(object):
    """
    Plots graphs based on the results of an IOzone run.

    Plots graphs based on the results of an IOzone run. Uses gnuplot to
    generate the graphs.
    """
    def __init__(self, results_file, output_dir):
        self.active = True
        try:
            self.gnuplot = os_dep.command("gnuplot")
        except:
            logging.error("Command gnuplot not found, disabling graph "
                          "generation")
            self.active = False

        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)
        self.output_dir = output_dir

        if not os.path.isfile(results_file):
            logging.error("Invalid file %s provided, disabling graph "
                          "generation", results_file)
            self.active = False
            self.results_file = None
        else:
            self.results_file = results_file
            self.generate_data_source()


    def generate_data_source(self):
        """
        Creates data file without headers for gnuplot consumption.
        """
        results_file = open(self.results_file, 'r')
        self.datasource = os.path.join(self.output_dir, '3d-datasource')
        datasource = open(self.datasource, 'w')
        for line in results_file.readlines():
            fields = line.split()
            if len(fields) != 15:
                continue
            try:
                values = [int(i) for i in fields]
                datasource.write(line)
            except ValueError:
                continue
        datasource.close()


    def plot_2d_graphs(self):
        """
        For each one of the throughput parameters, generate a set of gnuplot
        commands that will create a parametric surface with file size vs.
        record size vs. throughput.
        """
        datasource_2d = os.path.join(self.output_dir, '2d-datasource-file')
        for index, label in zip(range(2, 15), _LABELS[2:]):
            commands_path = os.path.join(self.output_dir, '2d-%s.do' % label)
            commands = ""
            commands += "set title 'Iozone performance: %s'\n" % label
            commands += "set logscale x\n"
            commands += "set xlabel 'File size (KB)'\n"
            commands += "set ylabel 'Througput (MB/s)'\n"
            commands += "set terminal png small size 450 350\n"
            commands += "set output '%s'\n" % os.path.join(self.output_dir,
                                                           '2d-%s.png' % label)
            commands += ("plot '%s' using 1:%s title '%s' with lines \n" %
                         (datasource_2d, index, label))
            commands_file = open(commands_path, 'w')
            commands_file.write(commands)
            commands_file.close()
            try:
                utils.system("%s %s" % (self.gnuplot, commands_path))
            except error.CmdError:
                logging.error("Problem plotting from commands file %s",
                              commands_path)


    def plot_3d_graphs(self):
        """
        For each one of the throughput parameters, generate a set of gnuplot
        commands that will create a parametric surface with file size vs.
        record size vs. throughput.
        """
        for index, label in zip(range(1, 14), _LABELS[2:]):
            commands_path = os.path.join(self.output_dir, '%s.do' % label)
            commands = ""
            commands += "set title 'Iozone performance: %s'\n" % label
            commands += "set grid lt 2 lw 1\n"
            commands += "set surface\n"
            commands += "set parametric\n"
            commands += "set xtics\n"
            commands += "set ytics\n"
            commands += "set logscale x 2\n"
            commands += "set logscale y 2\n"
            commands += "set logscale z\n"
            commands += "set xrange [2.**5:2.**24]\n"
            commands += "set xlabel 'File size (KB)'\n"
            commands += "set ylabel 'Record size (KB)'\n"
            commands += "set zlabel 'Througput (KB/s)'\n"
            commands += "set data style lines\n"
            commands += "set dgrid3d 80,80, 3\n"
            commands += "set terminal png small size 900 700\n"
            commands += "set output '%s'\n" % os.path.join(self.output_dir,
                                                           '%s.png' % label)
            commands += ("splot '%s' using 1:2:%s title '%s'\n" %
                         (self.datasource, index, label))
            commands_file = open(commands_path, 'w')
            commands_file.write(commands)
            commands_file.close()
            try:
                utils.system("%s %s" % (self.gnuplot, commands_path))
            except error.CmdError:
                logging.error("Problem plotting from commands file %s",
                              commands_path)


    def plot_all(self):
        """
        Plot all graphs that are to be plotted, provided that we have gnuplot.
        """
        if self.active:
            self.plot_2d_graphs()
            self.plot_3d_graphs()


class AnalyzerLoggingConfig(logging_config.LoggingConfig):
    def configure_logging(self, results_dir=None, verbose=False):
        super(AnalyzerLoggingConfig, self).configure_logging(use_console=True,
                                                        verbose=verbose)


if __name__ == "__main__":
    parser = optparse.OptionParser("usage: %prog [options] [filenames]")
    options, args = parser.parse_args()

    logging_manager.configure_logging(AnalyzerLoggingConfig())

    if args:
        filenames = args
    else:
        parser.print_help()
        sys.exit(1)

    if len(args) > 2:
        parser.print_help()
        sys.exit(1)

    o = os.path.join(os.getcwd(),
                     "iozone-graphs-%s" % time.strftime('%Y-%m-%d-%H.%M.%S'))
    if not os.path.isdir(o):
        os.makedirs(o)

    a = IOzoneAnalyzer(list_files=filenames, output_dir=o)
    a.analyze()
    p = IOzonePlotter(results_file=filenames[0], output_dir=o)
    p.plot_all()
