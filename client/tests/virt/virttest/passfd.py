'''
passfd.py: Python library to pass file descriptors across UNIX domain sockets

This simple extension provides two functions to pass and receive file
descriptors across UNIX domain sockets, using the BSD-4.3+ sendmsg() and
recvmsg() interfaces.

Direct bindings to sendmsg and recvmsg are not provided, as the API does
not map nicely into Python.

Please note that this only supports BSD-4.3+ style file descriptor
passing, and was only tested on Linux. Patches are welcomed!

For more information, see one of the R. Stevens' books:
 - Richard Stevens: Unix Network Programming, Prentice Hall, 1990;
   chapter 6.10

 - Richard Stevens: Advanced Programming in the UNIX Environment,
   Addison-Wesley, 1993; chapter 15.3
'''

#
# Copyright (C) 2010 Martin Ferrari <martin.ferrari@gmail.com>
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#

import socket
import _passfd


def __check_socket(sock):
    if hasattr(sock, 'family') and sock.family != socket.AF_UNIX:
        raise ValueError("Only AF_UNIX sockets are allowed")

    if hasattr(sock, 'fileno'):
        sock = sock.fileno()

    if not isinstance(sock, int):
        raise TypeError("An socket object or file descriptor was expected")

    return sock


def __check_fd(fd):
    try:
        fd = fd.fileno()
    except AttributeError:
        pass
    if not isinstance(fd, int):
        raise TypeError("An file object or file descriptor was expected")

    return fd


def sendfd(sock, fd, message="NONE"):
    """
    Sends a message and piggybacks a file descriptor via a Unix domain socket

    Note that the file descriptor cannot be sent by itself, at least
    one byte of payload needs to be sent also.

    @param sock: socket object or file descriptor for an AF_UNIX socket
    @param fd: file object or file descriptor to pass
    @param message: message to send
    @return: On success, sendfd returns the number of bytes sent, not including
    the file descriptor nor the control data.  If there was no message
    to send, 0 is returned.
    """
    return _passfd.sendfd(__check_socket(sock), __check_fd(fd), message)


def recvfd(sock, msg_buf = 4096):
    """
    Receive a message and a file descriptor from a Unix domain socket.

    @param sock: file descriptor or socket object for an AF_UNIX socket
    @param buffersize: maximum message size to receive
    @return: On success, recvfd returns a tuple containing the received
    file descriptor and message
    @raise OSError is raised if recvmsg fails
    @raise RuntimeError is raised if the received data does not carry
    exactly one file descriptor, or if the received file descriptor
    is not valid.
    """
    (ret, msg) = _passfd.recvfd(__check_socket(sock), msg_buf)
    print ret
    print msg

    # -1 should raise OSError
    if ret == -2:
        raise RuntimeError("The message received did not contain exactly one" +
                " file descriptor")
    if ret == -3:
        raise RuntimeError("The received file descriptor is not valid")
    assert ret >= 0

    return (ret, msg)
