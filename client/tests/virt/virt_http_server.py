import os, posixpath, urlparse, urllib, logging
import BaseHTTPServer, SimpleHTTPServer


class HTTPRequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):

    def do_GET(self):
        """
        Serve a GET request.
        """
        range = self.parse_header_byte_range()
        if range:
            f = self.send_head_range(range[0], range[1])
            if f:
                self.copyfile_range(f, self.wfile, range[0], range[1])
                f.close()
        else:
            f = self.send_head()
            if f:
                self.copyfile(f, self.wfile)
                f.close()


    def parse_header_byte_range(self):
        range_param = 'Range'
        range_discard = 'bytes='
        if self.headers.has_key(range_param):
            range = self.headers.get(range_param)
            if range.startswith(range_discard):
                range = range[len(range_discard):]
                begin, end = range.split('-')
                return (int(begin), int(end))
        return None


    def copyfile_range(self, source_file, output_file, range_begin, range_end):
        """
        Copies a range of a file to destination.
        """
        range_size = range_end - range_begin + 1
        source_file.seek(range_begin)
        buf = source_file.read(range_size)
        output_file.write(buf)


    def send_head_range(self, range_begin, range_end):
        path = self.translate_path(self.path)
        f = None
        if os.path.isdir(path):
            for index in "index.html", "index.htm":
                index = os.path.join(path, index)
                if os.path.exists(index):
                    path = index
                    break
            else:
                return self.list_directory(path)
        ctype = self.guess_type(path)
        try:
            # Always read in binary mode. Opening files in text mode may cause
            # newline translations, making the actual size of the content
            # transmitted *less* than the content-length!
            f = open(path, 'rb')
        except IOError:
            self.send_error(404, "File not found")
            return None
        self.send_response(206, "Partial Content")
        file_size = str(os.fstat(f.fileno())[6])
        range_size = str(range_end - range_begin + 1)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", range_size)
        self.send_header("Content-Range", "bytes %s-%s/%s" % (range_begin,
                                                              range_end,
                                                              file_size))
        self.send_header("Content-type", ctype)
        self.end_headers()
        return f


    def translate_path(self, path):
        """
        Translate a /-separated PATH to the local filename syntax.

        Components that mean special things to the local file system
        (e.g. drive or directory names) are ignored.  (XXX They should
        probably be diagnosed.)

        """
        # abandon query parameters
        path = urlparse.urlparse(path)[2]
        path = posixpath.normpath(urllib.unquote(path))
        words = path.split('/')
        words = filter(None, words)
        path = self.server.cwd
        for word in words:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (os.curdir, os.pardir): continue
            path = os.path.join(path, word)
        return path


    def address_string(self):
        '''
        This HTTP server does not care about name resolution for the requests

        The first reason is that most of the times our clients are going to be
        virtual machines without a proper name resolution setup. Also, by not
        resolving names, we should be a bit faster and be resilient about
        misconfigured or resilient name servers.
        '''
        return self.client_address[0]


    def log_message(self, format, *args):
        logging.debug("builtin http server handling request from %s: %s" %
                      (self.address_string(), format%args))


def http_server(port=8000, cwd=None, terminate_callable=None):
    http = BaseHTTPServer.HTTPServer(('', port), HTTPRequestHandler)
    if cwd is None:
        cwd = os.getcwd()
    http.cwd = cwd

    while True:
        if terminate_callable is not None:
            terminate = terminate_callable()
        else:
            terminate = False

        if not terminate:
            http.handle_request()


if __name__ == '__main__':
    http_server()
