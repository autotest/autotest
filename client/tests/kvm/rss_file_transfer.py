#!/usr/bin/python
"""
Client for file transfer services offered by RSS (Remote Shell Server).

@author: Michael Goldish (mgoldish@redhat.com)
@copyright: 2008-2010 Red Hat Inc.
"""

import socket, struct, time, sys, os, glob

# Globals
CHUNKSIZE = 65536

# Protocol message constants
RSS_MAGIC           = 0x525353
RSS_OK              = 1
RSS_ERROR           = 2
RSS_UPLOAD          = 3
RSS_DOWNLOAD        = 4
RSS_SET_PATH        = 5
RSS_CREATE_FILE     = 6
RSS_CREATE_DIR      = 7
RSS_LEAVE_DIR       = 8
RSS_DONE            = 9

# See rss.cpp for protocol details.


class FileTransferError(Exception):
    pass


class FileTransferConnectError(FileTransferError):
    pass


class FileTransferTimeoutError(FileTransferError):
    pass


class FileTransferProtocolError(FileTransferError):
    pass


class FileTransferSendError(FileTransferError):
    pass


class FileTransferServerError(FileTransferError):
    pass


class FileTransferNotFoundError(FileTransferError):
    pass


class FileTransferClient(object):
    """
    Connect to a RSS (remote shell server) and transfer files.
    """

    def __init__(self, address, port, timeout=10):
        """
        Connect to a server.

        @param address: The server's address
        @param port: The server's port
        @param timeout: Time duration to wait for connection to succeed
        @raise FileTransferConnectError: Raised if the connection fails
        @raise FileTransferProtocolError: Raised if an incorrect magic number
                is received
        """
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(timeout)
        try:
            self._socket.connect((address, port))
        except socket.error:
            raise FileTransferConnectError("Could not connect to server")
        try:
            if self._receive_msg(timeout) != RSS_MAGIC:
                raise FileTransferConnectError("Received wrong magic number")
        except FileTransferTimeoutError:
            raise FileTransferConnectError("Timeout expired while waiting to "
                                           "receive magic number")
        self._send(struct.pack("=i", CHUNKSIZE))


    def __del__(self):
        self.close()


    def close(self):
        """
        Close the connection.
        """
        self._socket.close()


    def _send(self, str):
        try:
            self._socket.sendall(str)
        except socket.error:
            raise FileTransferSendError("Could not send data to server")


    def _receive(self, size, timeout=10):
        strs = []
        end_time = time.time() + timeout
        while size > 0:
            try:
                self._socket.settimeout(max(0.0001, end_time - time.time()))
                data = self._socket.recv(size)
            except socket.timeout:
                raise FileTransferTimeoutError("Timeout expired while "
                                               "receiving data from server")
            except socket.error:
                raise FileTransferProtocolError("Error receiving data from "
                                                "server")
            if not data:
                raise FileTransferProtocolError("Connection closed "
                                                "unexpectedly")
            strs.append(data)
            size -= len(data)
        return "".join(strs)


    def _send_packet(self, str):
        self._send(struct.pack("=I", len(str)))
        self._send(str)


    def _receive_packet(self, timeout=10):
        size = struct.unpack("=I", self._receive(4))[0]
        return self._receive(size, timeout)


    def _send_file_chunks(self, filename, timeout=30):
        f = open(filename, "rb")
        try:
            end_time = time.time() + timeout
            while time.time() < end_time:
                data = f.read(CHUNKSIZE)
                self._send_packet(data)
                if len(data) < CHUNKSIZE:
                    break
            else:
                raise FileTransferTimeoutError("Timeout expired while sending "
                                               "file %s" % filename)
        finally:
            f.close()


    def _receive_file_chunks(self, filename, timeout=30):
        f = open(filename, "wb")
        try:
            end_time = time.time() + timeout
            while True:
                try:
                    data = self._receive_packet(end_time - time.time())
                except FileTransferTimeoutError:
                    raise FileTransferTimeoutError("Timeout expired while "
                                                   "receiving file %s" %
                                                   filename)
                except FileTransferProtocolError:
                    raise FileTransferProtocolError("Error receiving file %s" %
                                                    filename)
                f.write(data)
                if len(data) < CHUNKSIZE:
                    break
        finally:
            f.close()


    def _send_msg(self, msg, timeout=10):
        self._send(struct.pack("=I", msg))


    def _receive_msg(self, timeout=10):
        s = self._receive(4, timeout)
        return struct.unpack("=I", s)[0]


    def _handle_transfer_error(self):
        # Save original exception
        e = sys.exc_info()
        try:
            # See if we can get an error message
            msg = self._receive_msg()
        except FileTransferError:
            # No error message -- re-raise original exception
            raise e[0], e[1], e[2]
        if msg == RSS_ERROR:
            errmsg = self._receive_packet()
            raise FileTransferServerError("Server said: %s" % errmsg)
        raise e[0], e[1], e[2]


class FileUploadClient(FileTransferClient):
    """
    Connect to a RSS (remote shell server) and upload files or directory trees.
    """

    def __init__(self, address, port, timeout=10):
        """
        Connect to a server.

        @param address: The server's address
        @param port: The server's port
        @param timeout: Time duration to wait for connection to succeed
        @raise FileTransferConnectError: Raised if the connection fails
        @raise FileTransferProtocolError: Raised if an incorrect magic number
                is received
        @raise FileTransferSendError: Raised if the RSS_UPLOAD message cannot
                be sent to the server
        """
        super(FileUploadClient, self).__init__(address, port, timeout)
        self._send_msg(RSS_UPLOAD)


    def _upload_file(self, path, end_time):
        if os.path.isfile(path):
            self._send_msg(RSS_CREATE_FILE)
            self._send_packet(os.path.basename(path))
            self._send_file_chunks(path, max(0, end_time - time.time()))
        elif os.path.isdir(path):
            self._send_msg(RSS_CREATE_DIR)
            self._send_packet(os.path.basename(path))
            for filename in os.listdir(path):
                self._upload_file(os.path.join(path, filename), end_time)
            self._send_msg(RSS_LEAVE_DIR)


    def upload(self, src_pattern, dst_path, timeout=600):
        """
        Send files or directory trees to the server.
        The semantics of src_pattern and dst_path are similar to those of scp.
        For example, the following are OK:
            src_pattern='/tmp/foo.txt', dst_path='C:\\'
                (uploads a single file)
            src_pattern='/usr/', dst_path='C:\\Windows\\'
                (uploads a directory tree recursively)
            src_pattern='/usr/*', dst_path='C:\\Windows\\'
                (uploads all files and directory trees under /usr/)
        The following is not OK:
            src_pattern='/tmp/foo.txt', dst_path='C:\\Windows\\*'
                (wildcards are only allowed in src_pattern)

        @param src_pattern: A path or wildcard pattern specifying the files or
                directories to send to the server
        @param dst_path: A path in the server's filesystem where the files will
                be saved
        @param timeout: Time duration in seconds to wait for the transfer to
                complete
        @raise FileTransferTimeoutError: Raised if timeout expires
        @raise FileTransferServerError: Raised if something goes wrong and the
                server sends an informative error message to the client
        @note: Other exceptions can be raised.
        """
        end_time = time.time() + timeout
        try:
            try:
                self._send_msg(RSS_SET_PATH)
                self._send_packet(dst_path)
                matches = glob.glob(src_pattern)
                for filename in matches:
                    self._upload_file(os.path.abspath(filename), end_time)
                self._send_msg(RSS_DONE)
            except FileTransferTimeoutError:
                raise
            except FileTransferError:
                self._handle_transfer_error()
            else:
                # If nothing was transferred, raise an exception
                if not matches:
                    raise FileTransferNotFoundError("Pattern %s does not "
                                                    "match any files or "
                                                    "directories" %
                                                    src_pattern)
                # Look for RSS_OK or RSS_ERROR
                msg = self._receive_msg(max(0, end_time - time.time()))
                if msg == RSS_OK:
                    return
                elif msg == RSS_ERROR:
                    errmsg = self._receive_packet()
                    raise FileTransferServerError("Server said: %s" % errmsg)
                else:
                    # Neither RSS_OK nor RSS_ERROR found
                    raise FileTransferProtocolError("Received unexpected msg")
        except:
            # In any case, if the transfer failed, close the connection
            self.close()
            raise


class FileDownloadClient(FileTransferClient):
    """
    Connect to a RSS (remote shell server) and download files or directory trees.
    """

    def __init__(self, address, port, timeout=10):
        """
        Connect to a server.

        @param address: The server's address
        @param port: The server's port
        @param timeout: Time duration to wait for connection to succeed
        @raise FileTransferConnectError: Raised if the connection fails
        @raise FileTransferProtocolError: Raised if an incorrect magic number
                is received
        @raise FileTransferSendError: Raised if the RSS_UPLOAD message cannot
                be sent to the server
        """
        super(FileDownloadClient, self).__init__(address, port, timeout)
        self._send_msg(RSS_DOWNLOAD)


    def download(self, src_pattern, dst_path, timeout=600):
        """
        Receive files or directory trees from the server.
        The semantics of src_pattern and dst_path are similar to those of scp.
        For example, the following are OK:
            src_pattern='C:\\foo.txt', dst_path='/tmp'
                (downloads a single file)
            src_pattern='C:\\Windows', dst_path='/tmp'
                (downloads a directory tree recursively)
            src_pattern='C:\\Windows\\*', dst_path='/tmp'
                (downloads all files and directory trees under C:\\Windows)
        The following is not OK:
            src_pattern='C:\\Windows', dst_path='/tmp/*'
                (wildcards are only allowed in src_pattern)

        @param src_pattern: A path or wildcard pattern specifying the files or
                directories, in the server's filesystem, that will be sent to
                the client
        @param dst_path: A path in the local filesystem where the files will
                be saved
        @param timeout: Time duration in seconds to wait for the transfer to
                complete
        @raise FileTransferTimeoutError: Raised if timeout expires
        @raise FileTransferServerError: Raised if something goes wrong and the
                server sends an informative error message to the client
        @note: Other exceptions can be raised.
        """
        dst_path = os.path.abspath(dst_path)
        end_time = time.time() + timeout
        file_count = 0
        dir_count = 0
        try:
            try:
                self._send_msg(RSS_SET_PATH)
                self._send_packet(src_pattern)
            except FileTransferError:
                self._handle_transfer_error()
            while True:
                msg = self._receive_msg()
                if msg == RSS_CREATE_FILE:
                    # Receive filename and file contents
                    filename = self._receive_packet()
                    if os.path.isdir(dst_path):
                        dst_path = os.path.join(dst_path, filename)
                    self._receive_file_chunks(
                            dst_path, max(0, end_time - time.time()))
                    dst_path = os.path.dirname(dst_path)
                    file_count += 1
                elif msg == RSS_CREATE_DIR:
                    # Receive dirname and create the directory
                    dirname = self._receive_packet()
                    if os.path.isdir(dst_path):
                        dst_path = os.path.join(dst_path, dirname)
                    if not os.path.isdir(dst_path):
                        os.mkdir(dst_path)
                    dir_count += 1
                elif msg == RSS_LEAVE_DIR:
                    # Return to parent dir
                    dst_path = os.path.dirname(dst_path)
                elif msg == RSS_DONE:
                    # Transfer complete
                    if not file_count and not dir_count:
                        raise FileTransferNotFoundError("Pattern %s does not "
                                                        "match any files or "
                                                        "directories that "
                                                        "could be downloaded" %
                                                        src_pattern)
                    break
                elif msg == RSS_ERROR:
                    # Receive error message and abort
                    errmsg = self._receive_packet()
                    raise FileTransferServerError("Server said: %s" % errmsg)
                else:
                    # Unexpected msg
                    raise FileTransferProtocolError("Received unexpected msg")
        except:
            # In any case, if the transfer failed, close the connection
            self.close()
            raise


def main():
    import optparse

    usage = "usage: %prog [options] address port src_pattern dst_path"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-d", "--download",
                      action="store_true", dest="download",
                      help="download files from server")
    parser.add_option("-u", "--upload",
                      action="store_true", dest="upload",
                      help="upload files to server")
    parser.add_option("-t", "--timeout",
                      type="int", dest="timeout", default=3600,
                      help="transfer timeout")
    options, args = parser.parse_args()
    if options.download == options.upload:
        parser.error("you must specify either -d or -u")
    if len(args) != 4:
        parser.error("incorrect number of arguments")
    address, port, src_pattern, dst_path = args
    port = int(port)

    if options.download:
        client = FileDownloadClient(address, port)
        client.download(src_pattern, dst_path, timeout=options.timeout)
        client.close()
    elif options.upload:
        client = FileUploadClient(address, port)
        client.upload(src_pattern, dst_path, timeout=options.timeout)
        client.close()


if __name__ == "__main__":
    main()
