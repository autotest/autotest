import os, re, logging, SocketServer


SYSLOG_PORT = 514
DEFAULT_FORMAT = '[relayed from embedded syslog server (%s.%s)] %s'


def set_default_format(message_format):
    '''
    Changes the default message format

    @type message_format: string
    @param message_format: a message format string with 3 placeholders:
                           facility, priority and message.
    '''
    global DEFAULT_FORMAT
    DEFAULT_FORMAT = message_format


def get_default_format():
    '''
    Returns the current default message format
    '''
    return DEFAULT_FORMAT


class RequestHandler(SocketServer.BaseRequestHandler):
    '''
    A request handler that relays all received messages as DEBUG
    '''

    RECORD_RE = re.compile('\<(\d+)\>(.*)')

    (LOG_EMERG,
     LOG_ALERT,
     LOG_CRIT,
     LOG_ERR,
     LOG_WARNING,
     LOG_NOTICE,
     LOG_INFO,
     LOG_DEBUG) = range(8)

    (LOG_KERN,
     LOG_USER,
     LOG_MAIL,
     LOG_DAEMON,
     LOG_AUTH,
     LOG_SYSLOG,
     LOG_LPR,
     LOG_NEWS,
     LOG_UUCP,
     LOG_CRON,
     LOG_AUTHPRIV,
     LOG_FTP) = range(12)

    (LOG_LOCAL0,
     LOG_LOCAL1,
     LOG_LOCAL2,
     LOG_LOCAL3,
     LOG_LOCAL4,
     LOG_LOCAL5,
     LOG_LOCAL6,
     LOG_LOCAL7) = range(16, 24)

    PRIORITY_NAMES = {
        LOG_ALERT : "alert",
        LOG_CRIT : "critical",
        LOG_DEBUG : "debug",
        LOG_EMERG : "emerg",
        LOG_ERR : "err",
        LOG_INFO : "info",
        LOG_NOTICE : "notice",
        LOG_WARNING: "warning"
        }

    FACILITY_NAMES = {
        LOG_AUTH : "auth",
        LOG_AUTHPRIV : "authpriv",
        LOG_CRON : "cron",
        LOG_DAEMON : "daemon",
        LOG_FTP : "ftp",
        LOG_KERN : "kern",
        LOG_LPR : "lpr",
        LOG_MAIL : "mail",
        LOG_NEWS : "news",
        LOG_AUTH : "security",
        LOG_SYSLOG : "syslog",
        LOG_USER : "user",
        LOG_UUCP : "uucp",
        LOG_LOCAL0 : "local0",
        LOG_LOCAL1 : "local1",
        LOG_LOCAL2 : "local2",
        LOG_LOCAL3 : "local3",
        LOG_LOCAL4 : "local4",
        LOG_LOCAL5 : "local5",
        LOG_LOCAL6 : "local6",
        LOG_LOCAL7 : "local7",
        }


    def decodeFacilityPriority(self, priority):
        '''
        Decode both the facility and priority embedded in a syslog message

        @type priority: integer
        @param priority: an integer with facility and priority encoded
        @return: a tuple with two strings
        '''
        f = priority >> 3
        p = priority & 7
        return (self.FACILITY_NAMES.get(f, 'unknown'),
                self.PRIORITY_NAMES.get(p, 'unknown'))


    def log(self, data, message_format=None):
        '''
        Logs the received message as a DEBUG message
        '''
        match = self.RECORD_RE.match(data)
        if match:
            if message_format is None:
                message_format = get_default_format()
            pri = int(match.groups()[0])
            msg = match.groups()[1]
            (facility_name, priority_name) = self.decodeFacilityPriority(pri)
            logging.debug(message_format, facility_name, priority_name, msg)


class RequestHandlerTcp(RequestHandler):
    def handle(self):
        '''
        Handles a single request
        '''
        data = self.request.recv(4096)
        self.log(data)


class RequestHandlerUdp(RequestHandler):
    def handle(self):
        '''
        Handles a single request
        '''
        data = self.request[0]
        self.log(data)


class SysLogServerUdp(SocketServer.UDPServer):
    def __init__(self, address):
        SocketServer.UDPServer.__init__(self, address, RequestHandlerUdp)


class SysLogServerTcp(SocketServer.TCPServer):
    def __init__(self, address):
        SocketServer.TCPServer.__init__(self, address, RequestHandlerTcp)


def syslog_server(address='', port=SYSLOG_PORT,
                  tcp=True, terminate_callable=None):
    if tcp:
        klass = SysLogServerTcp
    else:
        klass = SysLogServerUdp
    syslog = klass((address, port))

    while True:
        if terminate_callable is not None:
            terminate = terminate_callable()
        else:
            terminate = False

        if not terminate:
            syslog.handle_request()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    syslog_server()
