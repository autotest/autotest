#!/usr/bin/python
"""
Module used to parse the autotest job status file and generate a JSON file.

Optionally, we can also generate reports (HTML)
"""
import os
import datetime
import time
import optparse
import logging
import sys
import re

try:
    import autotest.common as common
except ImportError:
    import common

try:
    import json
except ImportError:
    from autotest.client.shared.backports import simplejson as json

try:
    import jsontemplate
except ImportError:
    from autotest.client.shared import jsontemplate


from autotest.client.shared import base_job, settings, logging_manager
from autotest.client.shared import logging_config


class InvalidAutotestResultDirError(Exception):

    def __init__(self, directory):
        self.directory = directory

    def __str__(self):
        return ("Invalid Autotest results directory (missing status file): %s" %
                self.directory)


class InvalidOutputDirError(Exception):

    def __init__(self, directory):
        self.directory = directory

    def __str__(self):
        return "Parent dir %s of job report does not exist" % self.directory


def get_info_file(filename):
    """
    Gets the contents of an autotest info file.

    It also and highlights the file contents with possible problems.

    :param filename: Info file path.
    """
    data = ''
    errors = re.compile(r"\b(error|fail|failed)\b", re.IGNORECASE)
    if os.path.isfile(filename):
        f = open('%s' % filename, "r")
        lines = f.readlines()
        f.close()
        rx = re.compile('(\'|\")')
        for line in lines:
            new_line = rx.sub('', line)
            errors_found = errors.findall(new_line)
            if len(errors_found) > 0:
                data += '<font color=red>%s</font><br>' % str(new_line)
            else:
                data += '%s<br>' % str(new_line)
        if not data:
            data = 'No Information Found.<br>'
    else:
        data = 'File not found.<br>'
    return data


def parse_results_dir(results_dir, relative_links=True):
    """
    Parse a top level status file and produce a dictionary with job data.

    :param dirname: Autotest results directory path
    :return: Dictionary with job data.
    """
    job_data = {}
    op_data = {}

    res_dir = os.path.abspath(results_dir)

    status_file_name = os.path.join(results_dir, 'status')

    if not os.path.isfile(status_file_name):
        raise InvalidAutotestResultDirError(res_dir)

    file_obj = open(status_file_name, "r")
    status_lines = file_obj.readlines()
    file_obj.close()

    sysinfo_dir = os.path.join(results_dir, 'sysinfo')

    job_data['sysinfo'] = {
        'hostname': get_info_file(os.path.join(sysinfo_dir, 'hostname').strip()),
        'uname': get_info_file(os.path.join(sysinfo_dir, 'uname')),
        'cpuinfo': get_info_file(os.path.join(sysinfo_dir, 'cpuinfo')),
        'meminfo': get_info_file(os.path.join(sysinfo_dir, 'meminfo')),
        'df': get_info_file(os.path.join(sysinfo_dir, 'df')),
        'modules': get_info_file(os.path.join(sysinfo_dir, 'modules')),
        'gcc': get_info_file(os.path.join(sysinfo_dir, 'gcc_--version')),
        'dmidecode': get_info_file(os.path.join(sysinfo_dir, 'dmidecode')),
        'dmesg': get_info_file(os.path.join(sysinfo_dir, 'dmesg'))}

    job_data['results_dir'] = res_dir
    if relative_links:
        job_data['absolute_path'] = None
    else:
        job_data['absolute_path'] = res_dir

    # Initialize job pass state
    job_data['job_passed'] = True
    # Initialize operations counter
    job_data['operations_passed'] = 0
    job_data['operations_failed'] = 0
    # Format date and time to be displayed
    t = datetime.datetime.now()
    epoch_sec = time.mktime(t.timetuple())
    now = datetime.datetime.fromtimestamp(epoch_sec)
    job_data['report_generation_time'] = now.ctime()

    for line in status_lines:
        results_data = {}
        log_entry = base_job.status_log_entry.parse(line)
        if not log_entry:
            continue
        results_data['status_code'] = log_entry.status_code
        results_data['subdir'] = log_entry.subdir
        results_data['operation'] = log_entry.operation
        results_data['message'] = log_entry.message
        results_data['fields'] = log_entry.fields
        results_data['timestamp'] = log_entry.fields[log_entry.TIMESTAMP_FIELD]
        results_data['localtime'] = log_entry.fields[log_entry.LOCALTIME_FIELD]

        # If the operation's 'subdir' is None,
        # then this is a job (root) level event
        if results_data['subdir'] is None:
            key = 'job'
            update_dict = job_data
            try:
                update_dict[key]
            except KeyError:
                update_dict[key] = {}
                update_dict['operations'] = []

            if results_data['status_code'] == 'START':
                update_dict[key]['start'] = int(results_data['timestamp'])
                update_dict[key]['localtime'] = results_data['localtime']
            elif results_data['status_code'] != 'GOOD':
                # Check if the status is True (means operation succeeded)
                # or False (means operation failed)
                if not base_job.JOB_STATUSES[results_data['status_code']]:
                    job_data['job_passed'] = False

                update_dict[key]['end'] = int(results_data['timestamp'])
                update_dict[key]['duration'] = (update_dict[key]['end'] -
                                                update_dict[key]['start'])
                update_dict[key]['message'] = results_data['message']
                update_dict[key]['status_code'] = (
                    results_data['status_code'].split()[-1])

        # Otherwise, it is a test, or kernel configure/build, or reboot
        else:
            update_dict = op_data
            update_dict['subdir'] = results_data['subdir']

            if results_data['status_code'] == 'START':
                update_dict['start'] = int(results_data['timestamp'])
                update_dict['localtime'] = results_data['localtime']

            elif results_data['status_code'].startswith('END'):
                # Check if the status is True (means operation succeeded)
                # or False (means operation failed)
                if base_job.JOB_STATUSES[results_data['status_code']]:
                    job_data['operations_passed'] += 1
                else:
                    job_data['operations_failed'] += 1

                update_dict['end'] = int(results_data['timestamp'])
                update_dict['duration'] = (update_dict['end'] -
                                           update_dict['start'])
                update_dict['message'] = results_data['message']
                update_dict['status_code'] = (
                    results_data['status_code'].split()[-1])
                job_data['operations'].append(update_dict)
                op_data = {}

    # Now we will account the number of operations and PASS rate
    job_data['operations_executed'] = (job_data['operations_passed'] +
                                       job_data['operations_failed'])
    job_data['operations_pass_rate'] = float(100 *
                                             job_data['operations_passed'] / job_data['operations_executed'])

    return job_data


def generate_json_file(results_dir, relative_links=True):
    """
    Generate a JSON file with autotest job summary on a given results directory

    :param results_dir: Path to the results directory.
    """
    results_data = parse_results_dir(results_dir, relative_links)
    json_path = os.path.join(results_dir, 'status.json')
    json_file = open(json_path, 'w')
    json.dump(results_data, json_file)
    json_file.close()
    return json_path


def generate_html_report(results_dir, relative_links=True):
    """
    Render a job report HTML.

    All CSS and javascript are inlined, for more convenience.

    :param results_dir: Path to the results directory.
    """
    json_path = generate_json_file(results_dir, relative_links)
    json_fo = open(json_path, 'r')
    job_data = json.load(json_fo)

    templates_path = settings.settings.get_value("CLIENT", "job_templates_dir",
                                                 default="")

    if not templates_path:
        templates_path = os.path.join(common.client_dir, "shared", "templates")

    base_template_path = os.path.join(templates_path, "report.jsont")
    base_template = open(base_template_path, "r").read()
    css_path = os.path.join(templates_path, "media", "css", "report.css")
    css = open(css_path, "r").read()
    js1_path = os.path.join(templates_path, "media", "js", "mktree.js")
    js1 = open(js1_path, "r").read()
    js2_path = os.path.join(templates_path, "media", "js", "table.js")
    js2 = open(js2_path, "r").read()

    context = {}
    context['css'] = css
    context['table_js'] = js1
    context['maketree_js'] = js2
    context['job_data'] = job_data

    return jsontemplate.expand(base_template, context)


def write_html_report(results_dir, report_path=None):
    """
    Write an HTML file at report_path, with job data summary.

    If no report_path specified, generate one at results_dir/job_report.html.

    :param results_dir: Directory with test results.
    :param report_path: Path to a report file (optional).
    """
    default_report_path = os.path.join(results_dir, "job_report.html")
    if report_path is None:
        report_path = default_report_path

    relative_links = True
    if report_path != default_report_path:
        relative_links = False

    rendered_html = generate_html_report(results_dir, relative_links)

    report_dir = os.path.dirname(report_path)
    if not os.path.isdir(report_dir):
        raise InvalidOutputDirError(report_dir)

    html_result = open(report_path, "w")
    html_result.write(rendered_html)
    html_result.close()
    logging.info("Report successfully generated at %s", report_path)


dirname = os.path.dirname(sys.modules[__name__].__file__)
client_dir = os.path.abspath(os.path.join(dirname, ".."))
DEFAULT_RESULTS_DIR = os.path.join(client_dir, "results", "default")
DEFAULT_REPORT_PATH = os.path.join(DEFAULT_RESULTS_DIR, "job_report.html")


class ReportOptionParser(optparse.OptionParser):

    def __init__(self):
        optparse.OptionParser.__init__(self,
                                       usage="%prog [-r result_directory] [-f output_file]")
        self.add_option("-r", action="store", type="string",
                        dest="results_dir",
                        default=DEFAULT_RESULTS_DIR,
                        help="Autotest results dir where to generate an HTML "
                             "report at (optional). Default: %default")
        self.add_option("-f", action="store", type="string",
                        dest="report_path",
                        default=DEFAULT_REPORT_PATH,
                        help="Path to a report file (optional). If you pass a "
                             "value different than the default, the HTML will "
                             "link to the absolute paths of the results dir. "
                             "Default: %default")


class ReportLoggingConfig(logging_config.LoggingConfig):

    """
    Used with the sole purpose of providing convenient logging setup
    for this program.
    """

    def configure_logging(self, results_dir=None, verbose=False):
        super(ReportLoggingConfig, self).configure_logging(use_console=True,
                                                           verbose=verbose)


ERROR_INVALID_RESULT_DIR = 1
ERROR_INVALID_REPORT_PATH = 2
ERROR_WRONG_INPUT = 3


if __name__ == "__main__":
    logging_manager.configure_logging(ReportLoggingConfig(), verbose=True)
    parser = ReportOptionParser()
    options, args = parser.parse_args()

    if args:
        parser.print_help()
        sys.exit(ERROR_WRONG_INPUT)

    try:
        write_html_report(results_dir=options.results_dir,
                          report_path=options.report_path)
    except InvalidAutotestResultDirError, e:
        logging.error(e)
        sys.exit(ERROR_INVALID_RESULT_DIR)
    except InvalidOutputDirError, e:
        logging.error(e)
        sys.exit(ERROR_INVALID_REPORT_PATH)
