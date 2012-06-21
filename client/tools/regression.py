#!/usr/bin/python
"""
Program that parses standard format results,
compute and check regression bug.

@copyright: Red Hat 2011-2012
@author: Amos Kong <akong@redhat.com>
"""
import os, sys, re, commands, warnings, ConfigParser


class Sample():
    """ Collect test results in same environment to a sample """
    def __init__(self, files):
        self.files_dict = []
        self.desc = ""
        self.version = ""
        for i in range(len(files)):
            fd = open(files[i], "r")
            f = []
            desc = []
            ver = []
            for l in fd.readlines():
                if "#desc#" in l:
                    desc.append(l[6:])
                elif "#ver#" in l:
                    ver.append(l[5:])
                else:
                    f.append(l.strip())

            self.files_dict.append(f)
            fd.close()

        nrepeat = len(self.files_dict)
        nrepeat_re = '\$repeat_n'
        self.desc = "".join(desc) + """ - Every Avg line represents the average value based on *$repeat_n* repetitions of the same test,
   and the following SD line represents the Standard Deviation between the *$repeat_n* repetitions.
 - The Standard deviation is displayed as a percentage of the average.
 - The significance of the differences between the two averages is calculated using unpaired T-test that
   takes into account the SD of the averages.
 - The paired t-test is computed for the averages of same category.

"""
        self.desc = re.sub(nrepeat_re, str(nrepeat), self.desc)
        self.version = "".join(ver)

    def getAvg(self, avg_update=None):
        return self._process_files(self.files_dict, self._get_list_avg,
                                   avg_update=avg_update)

    def getAvgPercent(self, avgs_dict):
        return self._process_files(avgs_dict, self._get_augment_rate)

    def getSD(self):
        return self._process_files(self.files_dict, self._get_list_sd)

    def getSDRate(self, sds_dict):
        return self._process_files(sds_dict, self._get_rate)

    def getTtestPvalue(self, fs_dict1, fs_dict2, paired=None):
        """
        scipy lib is used to compute p-value of Ttest
        scipy: http://www.scipy.org/
        t-test: http://en.wikipedia.org/wiki/Student's_t-test
        """
        try:
            from scipy import stats
            import numpy as np
        except ImportError:
            print "No python scipy/numpy library installed!"
            return None

        ret = []
        s1 = self._process_files(fs_dict1, self._get_list_self, merge=False)
        s2 = self._process_files(fs_dict2, self._get_list_self, merge=False)
        # s*[line][col] contians items (line*col) of all sample files

        for line in range(len(s1)):
            tmp = []
            if type(s1[line]) != list:
                tmp = s1[line]
            else:
                if len(s1[line][0]) < 2:
                    continue
                for col in range(len(s1[line])):
                    avg1 = self._get_list_avg(s1[line][col])
                    avg2 = self._get_list_avg(s2[line][col])
                    sample1 = np.array(s1[line][col])
                    sample2 = np.array(s2[line][col])
                    warnings.simplefilter("ignore", RuntimeWarning)
                    if (paired):
                        (t, p) = stats.ttest_rel(sample1, sample2)
                    else:
                        (t, p) = stats.ttest_ind(sample1, sample2)
                    flag = " "
                    if p <= 0.05:
                        flag = "+"
                        if float(avg1) > float(avg2):
                            flag = "-"
                    tmp.append(flag + "%.3f" % (1 - p ))
                tmp = "|".join(tmp)
            ret.append(tmp)
        return ret

    def _get_rate(self, data):
        """ num2 / num1 * 100 """
        result = "0.0"
        if len(data) == 2 and float(data[0]) != 0:
            result = float(data[1]) / float(data[0]) * 100
            if result < 1:
                result = "%.2f%%" % result
            else:
                result = "%.0f%%" % result
        return result

    def _get_augment_rate(self, data):
        """ (num2 - num1) / num1 * 100 """
        result = "+0.0"
        if len(data) == 2 and float(data[0]) != 0:
            result = "%+.3f%%" % ((float(data[1]) - float(data[0]))
                                 / float(data[0]) * 100)
        return result

    def _get_list_sd(self, data):
        """
        sumX = x1 + x2 + ... + xn
        avgX = sumX / n
        sumSquareX = x1^2 + ... + xn^2
        SD = sqrt([sumSquareX - (n * (avgX ^ 2))] / (n - 1))
        """
        sum = sqsum = 0
        n = len(data)
        for i in data:
            sum += float(i)
            sqsum += float(i) ** 2
        avg = sum / n
        if avg == 0 or n == 1 or sqsum - (n * avg**2) <= 0:
            return "0.0"
        return "%.3f" % (((sqsum - (n * avg**2)) / (n - 1))**0.5)

    def _get_list_avg(self, data):
        """ Compute the average of list entries """
        sum = 0
        for i in data:
            sum += float(i)
        if is_int(str(data[0])):
            return "%d" % (sum / len(data))
        return "%.2f" % (sum / len(data))

    def _get_list_self(self, data):
        """ Use this to convert sample dicts """
        return data

    def _process_lines(self, files_dict, row, func, avg_update, merge):
        """ Use unified function to process same lines of different samples """
        lines = []
        ret = []

        for i in range(len(files_dict)):
            lines.append(files_dict[i][row].split("|"))
        for col in range(len(lines[0])):
            data_list = []
            for i in range(len(lines)):
                tmp = lines[i][col].strip()
                if is_int(tmp):
                    data_list.append(int(tmp))
                else:
                    data_list.append(float(tmp))
            ret.append(func(data_list))

        if avg_update:
            for i in avg_update.split('|'):
                l = i.split(',')
                ret[int(l[0])] = "%.2f" % (float(ret[int(l[1])]) /
                                           float(ret[int(l[2])]))
        if merge:
            return "|".join(ret)
        return ret

    def _process_files(self, files_dict, func, avg_update=None, merge=True):
        """
        Process dicts of sample files with assigned function,
        func has one list augment.
        """
        ret_lines = []
        for i in range(len(files_dict[0])):
            if re.findall("[a-zA-Z]", files_dict[0][i]):
                ret_lines.append(files_dict[0][i].strip())
            else:
                line = self._process_lines(files_dict, i, func, avg_update,
                                           merge)
                ret_lines.append(line)
        return ret_lines


def display(lists, rates, allpvalues, f, ignore_col, sum="Augment Rate",
            prefix0=None, prefix1=None, prefix2=None, prefix3=None):
    """
    Display lists data to standard format

    param lists: row data lists
    param rates: augment rates lists
    param f: result output file
    param ignore_col: do not display some columns
    param sum: compare result summary
    param prefix0: output prefix in head lines
    param prefix1: output prefix in Avg/SD lines
    param prefix2: output prefix in Diff Avg/P-value lines
    param prefix3: output prefix in total Sign line
    """
    def str_ignore(str, split=False):
        str = str.split("|")
        for i in range(ignore_col):
            str[i] = " "
        if split:
            return "|".join(str[ignore_col:])
        return "|".join(str)

    def tee_line(content, file, n=None):
        fd = open(file, "a")
        print content
        str = ""
        str += "<TR ALIGN=CENTER>"
        content = content.split("|")
        for i in range(len(content)):
            if n and i >= 2 and i < ignore_col+2:
                str += "<TD ROWSPAN=%d WIDTH=1%% >%s</TD>" % (n, content[i])
            else:
                str += "<TD WIDTH=1%% >%s</TD>" % content[i]
        str += "</TR>"
        fd.write(str + "\n")
        fd.close()

    for l in range(len(lists[0])):
        if not re.findall("[a-zA-Z]", lists[0][l]):
            break
    tee("<TABLE BORDER=1 CELLSPACING=1 CELLPADDING=1 width=10%><TBODY>",
        f)
    tee("<h3>== %s " % sum + "==</h3>", f)
    category = 0
    for i in range(len(lists[0])):
        for n in range(len(lists)):
            is_diff = False
            for j in range(len(lists)):
                if lists[0][i] != lists[j][i]:
                    is_diff = True
                if len(lists) == 1 and not re.findall("[a-zA-Z]", lists[j][i]):
                    is_diff = True

            pfix = prefix1[0]
            if len(prefix1) != 1:
                pfix = prefix1[n]
            if is_diff:
                if n == 0:
                    tee_line(pfix + lists[n][i], f, n=len(lists)+len(rates))
                else:
                    tee_line(pfix + str_ignore(lists[n][i], True), f)
            if not is_diff and n == 0:
                if '|' in lists[n][i]:
                    tee_line(prefix0 + lists[n][i], f)
                elif "Category:" in lists[n][i]:
                    if category != 0 and prefix3:
                        tee_line(prefix3 + str_ignore(
                                 allpvalues[category-1][0]), f)
                        tee("</TBODY></TABLE>", f)
                        tee("<br>", f)
                        tee("<TABLE BORDER=1 CELLSPACING=1 CELLPADDING=1 "
                            "width=10%><TBODY>", f)
                    category += 1
                    tee("<TH colspan=3 >%s</TH>" % lists[n][i], f)
                else:
                    tee("<TH colspan=3 >%s</TH>" % lists[n][i], f)
        for n in range(len(rates)):
            if lists[0][i] != rates[n][i] and not re.findall("[a-zA-Z]",
                                                             rates[n][i]):
                tee_line(prefix2[n] +  str_ignore(rates[n][i], True), f)
    if prefix3 and len(allpvalues[0]) > 0:
        tee_line(prefix3 + str_ignore(allpvalues[category-1][0]), f)
    tee("</TBODY></TABLE>", f)

def analyze(test, sample_list1, sample_list2, configfile):
    """ Compute averages/p-vales of two samples, print results nicely """
    config = ConfigParser.ConfigParser()
    config.read(configfile)
    ignore_col = int(config.get(test, "ignore_col"))
    avg_update = config.get(test, "avg_update")

    commands.getoutput("rm -f %s.*html" % test)
    s1 = Sample(sample_list1.split())
    avg1 = s1.getAvg(avg_update=avg_update)
    sd1 = s1.getSD()

    s2 = Sample(sample_list2.split())
    avg2 = s2.getAvg(avg_update=avg_update)
    sd2 = s2.getSD()

    sd1 = s1.getSDRate([avg1, sd1])
    sd2 = s1.getSDRate([avg2, sd2])
    avgs_rate = s1.getAvgPercent([avg1, avg2])

    navg1 = []
    navg2 = []
    allpvalues = []
    tmp1 = []
    tmp2 = []
    for i in range(len(avg1)):
        if not re.findall("[a-zA-Z]", avg1[i]):
            tmp1.append([avg1[i]])
            tmp2.append([avg2[i]])
        elif not "|" in avg1[i] and i != 0:
            navg1.append(tmp1)
            navg2.append(tmp2)
            tmp1 = []
            tmp2 = []
    navg1.append(tmp1)
    navg2.append(tmp2)

    for i in range(len(navg1)):
        allpvalues.append(s1.getTtestPvalue(navg1[i], navg2[i], True))

    pvalues = s1.getTtestPvalue(s1.files_dict, s2.files_dict, False)
    rlist = [avgs_rate]
    if pvalues:
        # p-value list isn't null
        rlist.append(pvalues)

    tee("<pre>####1. Description of setup#1\n" + s1.version + "</pre>",
        test+".html")
    tee("<pre>####2. Description of setup#2\n" + s2.version + "</pre>",
        test+".html")
    tee("<pre>" + s1.desc + "</pre>", test+".html")

    display([avg1, sd1, avg2, sd2], rlist, allpvalues, test+".html",
            ignore_col, sum="Regression Testing: %s" % test, prefix0="#|Tile|",
            prefix1=["1|Avg|", " |%SD|", "2|Avg|", " |%SD|"],
            prefix2=["-|%Diff between Avg|", "-|Significance|"],
            prefix3="-|Total Significance|")

    display(s1.files_dict, [avg1], [], test+".avg.html", ignore_col,
            sum="Raw data of sample 1", prefix0="#|Tile|",
            prefix1=[" |    |"],
            prefix2=["-|Avg |"], prefix3="")

    display(s2.files_dict, [avg2], [], test+".avg.html", ignore_col,
            sum="Raw data of sample 2", prefix0="#|Tile|",
            prefix1=[" |    |"],
            prefix2=["-|Avg |"], prefix3="")

def compare(testname, olddir, curdir, configfile='perf.conf'):
    """ Find result files from directories """
    config = ConfigParser.ConfigParser()
    config.read(configfile)
    result_file_pattern = config.get(testname, "result_file_pattern")

    def search_files(dir):
        cmd = 'find %s|grep "%s.*/%s"' % (dir, testname, result_file_pattern)
        print cmd
        return commands.getoutput(cmd)

    oldlist = search_files(olddir)
    newlist = search_files(curdir)
    if oldlist != "" or newlist != "":
        analyze(testname, oldlist, newlist, configfile)

def is_int(n):
    try:
        int(n)
        return True
    except ValueError:
        return False

def tee(content, file):
    """ Write content to standard output and file """
    fd = open(file, "a")
    fd.write(content + "\n")
    fd.close()
    print content



if __name__ == "__main__":
    if len(sys.argv) != 4:
        this = os.path.basename(sys.argv[0])
        print 'Usage: %s <testname> <dir1> <dir2>' % this
        sys.exit(1)
    compare(sys.argv[1], sys.argv[2], sys.argv[3])
