#!/usr/bin/python
"""
Program that parses standard format results,
compute and check regression bug.

:copyright: Red Hat 2011-2012
:author: Amos Kong <akong@redhat.com>
"""
import ConfigParser
import commands
import os
import re
import sys
import warnings

import MySQLdb


def exec_sql(cmd, conf="../../global_config.ini"):
    config = ConfigParser.ConfigParser()
    config.read(conf)
    user = config.get("AUTOTEST_WEB", "user")
    passwd = config.get("AUTOTEST_WEB", "password")
    db = config.get("AUTOTEST_WEB", "database")
    db_type = config.get("AUTOTEST_WEB", "db_type")
    if db_type != 'mysql':
        print("regression.py: only support mysql database!")
        sys.exit(1)

    conn = MySQLdb.connect(host="localhost", user=user,
                           passwd=passwd, db=db)
    cursor = conn.cursor()
    cursor.execute(cmd)
    rows = cursor.fetchall()
    lines = []
    for row in rows:
        line = []
        for c in row:
            line.append(str(c))
        lines.append(" ".join(line))

    cursor.close()
    conn.close()
    return lines


def get_test_keyval(jobid, keyname, default=''):
    idx = exec_sql("select job_idx from tko_jobs where afe_job_id=%s"
                   % jobid)[-1]
    test_idx = exec_sql('select test_idx from tko_tests where job_idx=%s'
                        % idx)[3]
    try:
        return exec_sql('select value from tko_test_attributes'
                        ' where test_idx=%s and attribute="%s"'
                        % (test_idx, keyname))[-1]
    except Exception:
        return default


class Sample(object):

    """ Collect test results in same environment to a sample """

    def __init__(self, type, arg):
        def generate_raw_table(test_dict):
            ret_dict = []
            tmp = []
            type = category = None
            for i in test_dict:
                line = i.split('|')[1:]
                if not type:
                    type = line[0:2]
                if type != line[0:2]:
                    ret_dict.append('|'.join(type + tmp))
                    type = line[0:2]
                    tmp = []
                if "e+" in line[-1]:
                    tmp.append("%.0f" % float(line[-1]))
                elif 'e-' in line[-1]:
                    tmp.append("%.2f" % float(line[-1]))
                elif not (re.findall("[a-zA-Z]", line[-1]) or is_int(line[-1])):
                    tmp.append("%.2f" % float(line[-1]))
                else:
                    tmp.append(line[-1])

                if category != i.split('|')[0]:
                    category = i.split('|')[0]
                    ret_dict.append("Category:" + category.strip())
                    ret_dict.append(self.categories)
            ret_dict.append('|'.join(type + tmp))
            return ret_dict

        if type == 'file':
            files = arg.split()
            self.files_dict = []
            for i in range(len(files)):
                fd = open(files[i], "r")
                f = []
                for line in fd.readlines():
                    line = line.strip()
                    if re.findall("^### ", line):
                        if "kvm-userspace-ver" in line:
                            self.kvmver = line.split(':')[-1]
                        elif "kvm_version" in line:
                            self.hostkernel = line.split(':')[-1]
                        elif "guest-kernel-ver" in line:
                            self.guestkernel = line.split(':')[-1]
                        elif "session-length" in line:
                            self.len = line.split(':')[-1]
                    else:
                        f.append(line.strip())
                self.files_dict.append(f)
                fd.close()
        elif type == 'database':
            jobid = arg
            self.kvmver = get_test_keyval(jobid, "kvm-userspace-ver")
            self.hostkernel = get_test_keyval(jobid, "kvm_version")
            self.guestkernel = get_test_keyval(jobid, "guest-kernel-ver")
            self.len = get_test_keyval(jobid, "session-length")
            self.categories = get_test_keyval(jobid, "category")

            idx = exec_sql("select job_idx from tko_jobs where afe_job_id=%s"
                           % jobid)[-1]
            data = exec_sql("select test_idx,iteration_key,iteration_value"
                            " from tko_perf_view where job_idx=%s" % idx)
            testidx = None
            job_dict = []
            test_dict = []
            for line in data:
                s = line.split()
                if not testidx:
                    testidx = s[0]
                if testidx != s[0]:
                    job_dict.append(generate_raw_table(test_dict))
                    test_dict = []
                    testidx = s[0]
                test_dict.append(' | '.join(s[1].split('--')[0:] + s[-1:]))

            job_dict.append(generate_raw_table(test_dict))
            self.files_dict = job_dict

        self.version = " userspace: %s\n host kernel: %s\n guest kernel: %s" % (
            self.kvmver, self.hostkernel, self.guestkernel)
        nrepeat = len(self.files_dict)
        if nrepeat < 2:
            print("`nrepeat' should be larger than 1!")
            sys.exit(1)

        self.desc = """ - Every Avg line represents the average value based on *%d* repetitions of the same test,
   and the following SD line represents the Standard Deviation between the *%d* repetitions.
 - The Standard deviation is displayed as a percentage of the average.
 - The significance of the differences between the two averages is calculated using unpaired T-test that
   takes into account the SD of the averages.
 - The paired t-test is computed for the averages of same category.

""" % (nrepeat, nrepeat)

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
            print("No python scipy/numpy library installed!")
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
                    flag = "+"
                    if float(avg1) > float(avg2):
                        flag = "-"
                    tmp.append(flag + "%.3f" % (1 - p))
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
            result = "%+.3f%%" % ((float(data[1]) - float(data[0])) /
                                  float(data[0]) * 100)
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
        if avg == 0 or n == 1 or sqsum - (n * avg ** 2) <= 0:
            return "0.0"
        return "%.3f" % (((sqsum - (n * avg ** 2)) / (n - 1)) ** 0.5)

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
                line = i.split(',')
                ret[int(line[0])] = "%.2f" % (float(ret[int(line[1])]) /
                                              float(ret[int(line[2])]))
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
        print(content)
        str = ""
        str += "<TR ALIGN=CENTER>"
        content = content.split("|")
        for i in range(len(content)):
            if n and i >= 2 and i < ignore_col + 2:
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
                    tee_line(pfix + lists[n][i], f, n=len(lists) + len(rates))
                else:
                    tee_line(pfix + str_ignore(lists[n][i], True), f)
            if not is_diff and n == 0:
                if '|' in lists[n][i]:
                    tee_line(prefix0 + lists[n][i], f)
                elif "Category:" in lists[n][i]:
                    if category != 0 and prefix3:
                        if len(allpvalues[category - 1]) > 0:
                            tee_line(prefix3 + str_ignore(
                                     allpvalues[category - 1][0]), f)
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
                tee_line(prefix2[n] + str_ignore(rates[n][i], True), f)
    if prefix3 and len(allpvalues[-1]) > 0:
        tee_line(prefix3 + str_ignore(allpvalues[category - 1][0]), f)
    tee("</TBODY></TABLE>", f)


def analyze(test, type, arg1, arg2, configfile):
    """ Compute averages/p-vales of two samples, print results nicely """
    config = ConfigParser.ConfigParser()
    config.read(configfile)
    ignore_col = int(config.get(test, "ignore_col"))
    avg_update = config.get(test, "avg_update")
    desc = config.get(test, "desc")

    def get_list(dir):
        result_file_pattern = config.get(test, "result_file_pattern")
        cmd = 'find %s|grep "%s.*/%s"' % (dir, test, result_file_pattern)
        print(cmd)
        return commands.getoutput(cmd)

    if type == 'file':
        arg1 = get_list(arg1)
        arg2 = get_list(arg2)

    commands.getoutput("rm -f %s.*html" % test)
    s1 = Sample(type, arg1)
    avg1 = s1.getAvg(avg_update=avg_update)
    sd1 = s1.getSD()

    s2 = Sample(type, arg2)
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
        elif 'Category' in avg1[i] and i != 0:
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

    desc = desc % s1.len

    tee("<pre>####1. Description of setup#1\n" + s1.version + "</pre>",
        test + ".html")
    tee("<pre>####2. Description of setup#2\n" + s2.version + "</pre>",
        test + ".html")
    tee("<pre>" + '\n'.join(desc.split('\\n')) + "</pre>", test + ".html")
    tee("<pre>" + s1.desc + "</pre>", test + ".html")

    display([avg1, sd1, avg2, sd2], rlist, allpvalues, test + ".html",
            ignore_col, sum="Regression Testing: %s" % test, prefix0="#|Tile|",
            prefix1=["1|Avg|", " |%SD|", "2|Avg|", " |%SD|"],
            prefix2=["-|%Diff between Avg|", "-|Significance|"],
            prefix3="-|Total Significance|")

    display(s1.files_dict, [avg1], [], test + ".avg.html", ignore_col,
            sum="Raw data of sample 1", prefix0="#|Tile|",
            prefix1=[" |    |"],
            prefix2=["-|Avg |"], prefix3="")

    display(s2.files_dict, [avg2], [], test + ".avg.html", ignore_col,
            sum="Raw data of sample 2", prefix0="#|Tile|",
            prefix1=[" |    |"],
            prefix2=["-|Avg |"], prefix3="")


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
    print(content)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        this = os.path.basename(sys.argv[0])
        print('Usage: %s <testname> file <dir1> <dir2>' % this)
        print('    or %s <testname> db <jobid1> <jobid2>' % this)
        sys.exit(1)
    analyze(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], 'perf.conf')
