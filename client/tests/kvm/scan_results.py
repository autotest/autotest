#!/usr/bin/python
"""
Program that parses the autotest results and return a nicely printed final test
result.

@copyright: Red Hat 2008-2009
"""

def parse_results(text):
    """
    Parse text containing Autotest results.

    @return: A list of result 4-tuples.
    """
    result_list = []
    start_time_list = []
    info_list = []

    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        parts = line.split("\t")

        # Found a START line -- get start time
        if (line.startswith("START") and len(parts) >= 5 and
            parts[3].startswith("timestamp")):
            start_time = float(parts[3].split("=")[1])
            start_time_list.append(start_time)
            info_list.append("")

        # Found an END line -- get end time, name and status
        elif (line.startswith("END") and len(parts) >= 5 and
              parts[3].startswith("timestamp")):
            end_time = float(parts[3].split("=")[1])
            start_time = start_time_list.pop()
            info = info_list.pop()
            test_name = parts[2]
            test_status = parts[0].split()[1]
            # Remove "kvm." prefix
            if test_name.startswith("kvm."):
                test_name = test_name[4:]
            result_list.append((test_name, test_status,
                                int(end_time - start_time), info))

        # Found a FAIL/ERROR/GOOD line -- get failure/success info
        elif (len(parts) >= 6 and parts[3].startswith("timestamp") and
              parts[4].startswith("localtime")):
            info_list[-1] = parts[5]

    return result_list


def print_result(result, name_width):
    """
    Nicely print a single Autotest result.

    @param result: a 4-tuple
    @param name_width: test name maximum width
    """
    if result:
        format = "%%-%ds    %%-10s %%-8s %%s" % name_width
        print format % result


def main(resfiles):
    result_lists = []
    name_width = 40

    for resfile in resfiles:
        try:
            text = open(resfile).read()
        except IOError:
            print "Bad result file: %s" % resfile
            continue
        results = parse_results(text)
        result_lists.append((resfile, results))
        name_width = max([name_width] + [len(r[0]) for r in results])

    print_result(("Test", "Status", "Seconds", "Info"), name_width)
    print_result(("----", "------", "-------", "----"), name_width)

    for resfile, results in result_lists:
        print "        (Result file: %s)" % resfile
        for r in results:
            print_result(r, name_width)


if __name__ == "__main__":
    import sys, glob

    resfiles = glob.glob("../../results/default/status*")
    if len(sys.argv) > 1:
        if sys.argv[1] == "-h" or sys.argv[1] == "--help":
            print "Usage: %s [result files]" % sys.argv[0]
            sys.exit(0)
        resfiles = sys.argv[1:]
    main(resfiles)
