import os, BaseHTTPServer, cgi, threading
import common
from autotest_lib.scheduler import scheduler_config

_PORT = 13467

_HEADER = """
<html>
<head><title>Scheduler status</title></head>
<body>
Actions:<br>
<a href="?reparse_config=1">Reparse global config values</a><br>
<br>
"""

_FOOTER = """
</body>
</html>
"""

class StatusServerRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def _send_headers(self):
        self.send_response(200, 'OK')
        self.send_header('Content-Type', 'text/html')
        self.end_headers()


    def _parse_arguments(self):
        path_parts = self.path.split('?', 1)
        if len(path_parts) == 1:
            return {}

        encoded_args = path_parts[1]
        return cgi.parse_qs(encoded_args)


    def _write_line(self, line=''):
        self.wfile.write(line + '<br>\n')


    def _write_field(self, field, value):
        self._write_line('%s=%s' % (field, value))


    def _write_all_fields(self):
        self._write_line('Config values:')
        for field in scheduler_config.SchedulerConfig.FIELDS:
            self._write_field(field, getattr(scheduler_config.config, field))
        self._write_line()


    def _execute_actions(self, arguments):
        if 'reparse_config' in arguments:
            scheduler_config.config.read_config()
            self._write_line('Updated config!')
        self._write_line()


    def do_GET(self):
        self._send_headers()
        self.wfile.write(_HEADER)

        arguments = self._parse_arguments()
        self._execute_actions(arguments)
        self._write_all_fields()

        self.wfile.write(_FOOTER)


class StatusServer(object):
    def __init__(self):
        self._address = ('', _PORT)
        self._httpd = BaseHTTPServer.HTTPServer(self._address,
                                                StatusServerRequestHandler)


    def _run(self):
        print 'Status server running on', self._address
        self._httpd.serve_forever()


    def start(self):
        self._thread = threading.Thread(target=self._run, name='status_server')
        self._thread.start()
