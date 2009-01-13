import os, BaseHTTPServer, cgi, threading, urllib
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


    def _write_drone(self, hostname):
        line = hostname
        if not self.server._drone_manager.is_drone_enabled(hostname):
            line += ' (disabled)'
        self._write_line(line)


    def _write_drone_list(self):
        self._write_line('Drones:')
        for hostname in self.server._drone_manager.drone_hostnames():
            self._write_drone(hostname)
        self._write_line()


    def _execute_actions(self, arguments):
        if 'reparse_config' in arguments:
            scheduler_config.config.read_config()
            self.server._drone_manager.refresh_disabled_drones()
            self._write_line('Reparsed config!')
        self._write_line()


    def do_GET(self):
        self._send_headers()
        self.wfile.write(_HEADER)

        arguments = self._parse_arguments()
        self._execute_actions(arguments)
        self._write_all_fields()
        self._write_drone_list()

        self.wfile.write(_FOOTER)


class StatusServer(BaseHTTPServer.HTTPServer):
    def __init__(self, drone_manager):
        address = ('', _PORT)
        # HTTPServer is an old-style class :(
        BaseHTTPServer.HTTPServer.__init__(self, address,
                                           StatusServerRequestHandler)
        self._shutting_down = False
        self._drone_manager = drone_manager


    def shutdown(self):
        if self._shutting_down:
            return
        print 'Shutting down server...'
        self._shutting_down = True
        # make one last request to awaken the server thread and make it exit
        urllib.urlopen('http://localhost:%s' % _PORT)


    def _serve_until_shutdown(self):
        print 'Status server running on', self.server_address
        while not self._shutting_down:
            self.handle_request()


    def start(self):
        self._thread = threading.Thread(target=self._serve_until_shutdown,
                                        name='status_server')
        self._thread.start()
