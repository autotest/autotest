import sys, re, time, commands

def tee(content, filename):
    """ Write content to standard output and file """
    fd = open(filename, "a")
    fd.write(content + "\n")
    fd.close()
    print content

class samples(object):
    def __init__(self, files):
        self.files_dict = []
        for i in range(len(files)):
            fd = open(files[i], "r")
            self.files_dict.append(fd.readlines())
            fd.close()

    def getAvg(self):
        return self._process(self.files_dict, self._get_list_avg)

    def getAvgPercent(self, avgs_dict):
        return self._process(avgs_dict, self._get_augment_rate)

    def getSD(self):
        return self._process(self.files_dict, self._get_list_sd)

    def getSDPercent(self, sds_dict):
        return self._process(sds_dict, self._get_percent)

    def _get_percent(self, data):
        """ num2 / num1 * 100 """
        result = "0.0"
        if len(data) == 2 and float(data[0]) != 0:
            result = "%.1f" % (float(data[1]) / float(data[0]) * 100)
        return result

    def _get_augment_rate(self, data):
        """ (num2 - num1) / num1 * 100 """
        result = "+0.0"
        if len(data) == 2 and float(data[0]) != 0:
            result = "%+.1f" % (((float(data[1]) - float(data[0]))
                                 / float(data[0])) * 100)
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
        if avg == 0 or n == 1:
            return "0.0"
        return "%.1f" % (((sqsum - (n * avg**2)) / (n - 1))**0.5)

    def _get_list_avg(self, data):
        """ Compute the average of list members """
        sum = 0
        for i in data:
            sum += float(i)
        if "." in data[0]:
            return "%.2f" % (sum / len(data))
        return "%d" % (sum / len(data))

    def _process_lines(self, files_dict, row, func):
        """ Process lines of different sample files with assigned method """
        lines = []
        ret_lines = []

        for i in range(len(files_dict)):
            lines.append(files_dict[i][row].split("|"))
        for col in range(len(lines[0])):
            data_list = []
            for i in range(len(lines)):
                data_list.append(lines[i][col].strip())
            ret_lines.append(func(data_list))
        return "|".join(ret_lines)

    def _process(self, files_dict, func):
        """ Process dicts of sample files with assigned method """
        ret_lines = []
        for i in range(len(files_dict[0])):
            if re.findall("[a-zA-Z]", files_dict[0][i]):
                ret_lines.append(files_dict[0][i].strip())
            else:
                line = self._process_lines(files_dict, i, func)
                ret_lines.append(line)
        return ret_lines


def display(lists, rate, f, summary="Augment Rate", prefix="% ", ignore_col=1):
    """
    Display lists data to standard format

    param lists: row data lists
    param rate: augment rate list
    param f: result output file
    param summary: compare result summary
    param prefix: output prefix in rate lines
    param ignore_col: do not display some columns
    """
    def format(list, str, ignore_col=0):
        """ Format the string width of list member """
        str = str.split("|")
        for l in range(len(list)):
            line = list[l].split("|")
            for col in range(len(line)):
                line[col] = line[col].rjust(len(str[col]), ' ')
                if not re.findall("[a-zA-Z]", line[col]) and col < ignore_col:
                    line[col] = " " * len(str[col])
            list[l] = "|".join(line)
        return list

    for l in range(len(lists[0])):
        if not re.findall("[a-zA-Z]", lists[0][l]):
            break
    tee("\n== %s " % summary + "="*(len(lists[0][l-1]) - len(summary) + 3) , f)
    for n in range(len(lists)):
        lists[n] = format(lists[n], lists[n][l-1])
    rate = format(rate, rate[l-1], ignore_col)
    for i in range(len(lists[0])):
        for n in range(len(lists)):
            is_diff = False
            for j in range(len(lists)):
                if lists[0][i] != lists[j][i]:
                    is_diff = True
            if is_diff or n==0:
                tee(' ' * len(prefix) + lists[n][i], f)
        if lists[0][i] != rate[i] and not re.findall("[a-zA-Z]", rate[i]):
            tee(prefix + rate[i], f)


def analyze(sample_list1, sample_list2, log_file="./result.txt"):
    """ Compute averages of two lists of files, compare and display results """

    commands.getoutput("rm -f %s" % log_file)
    tee(time.ctime(time.time()), log_file)
    s1 = samples(sample_list1.split())
    avg1 = s1.getAvg()
    sd1 = s1.getSD()
    s2 = samples(sample_list2.split())
    avg2 = s2.getAvg()
    sd2 = s2.getSD()
    sd1 = s1.getSDPercent([avg1, sd1])
    sd2 = s1.getSDPercent([avg2, sd2])
    display([avg1], sd1, log_file, summary="Avg1 SD Augment Rate",
                   prefix="%SD ")
    display([avg2], sd2, log_file, summary="Avg2 SD Augment Rate",
                   prefix="%SD ")
    avgs_rate = s1.getAvgPercent([avg1, avg2])
    display([avg1, avg2], avgs_rate, log_file, summary="AvgS Augment Rate",
                   prefix="%   ")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print 'Usage: python %s "$results list1" "$results list2" $log_file'\
              % sys.argv[0]
        sys.exit(1)
    analyze(sys.argv[1], sys.argv[2], sys.argv[3])
