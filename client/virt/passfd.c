/* vim:ts=4:sw=4:et:ai:sts=4
 *
 * passfd.c: Functions to pass file descriptors across UNIX domain sockets.
 *
 * Please note that this only supports BSD-4.3+ style file descriptor passing,
 * and was only tested on Linux. Patches are welcomed!
 *
 * Copyright © 2010 Martín Ferrari <martin.ferrari@gmail.com>
 *
 * Inspired by Socket::PassAccessRights, which is:
 *   Copyright (c) 2000 Sampo Kellomaki <sampo@iki.fi>
 *
 * For more information, see one of the R. Stevens' books:
 * - Richard Stevens: Unix Network Programming, Prentice Hall, 1990;
 *   chapter 6.10
 *
 * - Richard Stevens: Advanced Programming in the UNIX Environment,
 *   Addison-Wesley, 1993; chapter 15.3
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the Free
 * Software Foundation; either version 2 of the License, or (at your option)
 * any later version.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
 * more details.
 *
 * You should have received a copy of the GNU General Public License along with
 * this program; if not, write to the Free Software Foundation, Inc., 51
 * Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
 */

#include <Python.h>
#ifndef _GNU_SOURCE
# define _GNU_SOURCE
#endif
#include <sys/types.h>
#include <sys/socket.h>
#include <unistd.h>

int _sendfd(int sock, int fd, size_t len, const void *msg);
int _recvfd(int sock, size_t *len, void *buf);

/* Python wrapper for _sendfd */
static PyObject *
sendfd(PyObject *self, PyObject *args) {
    const char *message;
    char *buf;
    int ret, sock, fd, message_len;

    if(!PyArg_ParseTuple(args, "iis#", &sock, &fd, &message, &message_len))
        return NULL;

    /* I don't know if I need to make a copy of the message buffer for thread
     * safety, but let's do it just in case... */
    buf = strndup(message, (size_t)message_len);
    if(buf == NULL)
        return PyErr_SetFromErrno(PyExc_OSError);

    Py_BEGIN_ALLOW_THREADS;
    ret = _sendfd(sock, fd, message_len, message);
    Py_END_ALLOW_THREADS;

    free(buf);
    if(ret == -1)
        return PyErr_SetFromErrno(PyExc_OSError);
    return Py_BuildValue("i", ret);
}

/* Python wrapper for _recvfd */
static PyObject *
recvfd(PyObject *self, PyObject *args) {
    char *buffer;
    int ret, sock, buffersize = 4096;
    size_t _buffersize;
    PyObject *retval;

    if(!PyArg_ParseTuple(args, "i|i", &sock, &buffersize))
        return NULL;

    if((buffer = malloc(buffersize)) == NULL)
        return PyErr_SetFromErrno(PyExc_OSError);

    _buffersize = buffersize;

    Py_BEGIN_ALLOW_THREADS;
    ret = _recvfd(sock, &_buffersize, buffer);
    Py_END_ALLOW_THREADS;

    buffersize = (int)_buffersize;
    if(ret == -1) {
        free(buffer);
        return PyErr_SetFromErrno(PyExc_OSError);
    }
    retval = Py_BuildValue("is#", ret, buffer, buffersize);
    free(buffer);
    return retval;
}

static PyMethodDef methods[] = {
    {"sendfd", sendfd, METH_VARARGS, "rv = sendfd(sock, fd, message)"},
    {"recvfd", recvfd, METH_VARARGS, "(fd, message) = recvfd(sock, "
        "buffersize = 4096)"},
    {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC init_passfd(void) {
    PyObject *m;
    m = Py_InitModule("_passfd", methods);
    if (m == NULL)
        return;
}

/* Size of the cmsg including one file descriptor */
#define CMSG_SIZE CMSG_SPACE(sizeof(int))

/*
 * _sendfd(): send a message and piggyback a file descriptor.
 *
 * Note that the file descriptor cannot be sent by itself, at least one byte of
 * payload needs to be sent.
 *
 * Parameters:
 *  sock: AF_UNIX socket
 *  fd:   file descriptor to pass
 *  len:  length of the message
 *  msg:  the message itself
 *
 * Return value:
 *  On success, sendfd returns the number of characters from the message sent,
 *  the file descriptor information is not taken into account. If there was no
 *  message to send, 0 is returned. On error, -1 is returned, and errno is set
 *  appropriately.
 *
 */
int _sendfd(int sock, int fd, size_t len, const void *msg) {
    struct iovec iov[1];
    struct msghdr msgh;
    char buf[CMSG_SIZE];
    struct cmsghdr *h;
    int ret;

    /* At least one byte needs to be sent, for some reason (?) */
    if(len < 1)
        return 0;

    memset(&iov[0], 0, sizeof(struct iovec));
    memset(&msgh, 0, sizeof(struct msghdr));
    memset(buf, 0, CMSG_SIZE);

    msgh.msg_name       = NULL;
    msgh.msg_namelen    = 0;

    msgh.msg_iov        = iov;
    msgh.msg_iovlen     = 1;

    msgh.msg_control    = buf;
    msgh.msg_controllen = CMSG_SIZE;
    msgh.msg_flags      = 0;

    /* Message to be sent */
    iov[0].iov_base = (void *)msg;
    iov[0].iov_len  = len;

    /* Control data */
    h = CMSG_FIRSTHDR(&msgh);
    h->cmsg_len   = CMSG_LEN(sizeof(int));
    h->cmsg_level = SOL_SOCKET;
    h->cmsg_type  = SCM_RIGHTS;
    ((int *)CMSG_DATA(h))[0] = fd;

    ret = sendmsg(sock, &msgh, 0);
    return ret;
}
/*
 * _recvfd(): receive a message and a file descriptor.
 *
 * Parameters:
 *  sock: AF_UNIX socket
 *  len:  pointer to the length of the message buffer, modified on return
 *  buf:  buffer to contain the received buffer
 *
 * If len is 0 or buf is NULL, the received message is stored in a temporary
 * buffer and discarded later.
 *
 * Return value:
 *  On success, recvfd returns the received file descriptor, and len points to
 *  the size of the received message.
 *  If recvmsg fails, -1 is returned, and errno is set appropriately.
 *  If the received data does not carry exactly one file descriptor, -2 is
 *  returned. If the received file descriptor is not valid, -3 is returned.
 *
 */
int _recvfd(int sock, size_t *len, void *buf) {
    struct iovec iov[1];
    struct msghdr msgh;
    char cmsgbuf[CMSG_SIZE];
    char extrabuf[4096];
    struct cmsghdr *h;
    int st, fd;

    if(*len < 1 || buf == NULL) {
        /* For some reason, again, one byte needs to be received. (it would not
         * block?) */
        iov[0].iov_base = extrabuf;
        iov[0].iov_len  = sizeof(extrabuf);
    } else {
        iov[0].iov_base = buf;
        iov[0].iov_len  = *len;
    }

    msgh.msg_name       = NULL;
    msgh.msg_namelen    = 0;

    msgh.msg_iov        = iov;
    msgh.msg_iovlen     = 1;

    msgh.msg_control    = cmsgbuf;
    msgh.msg_controllen = CMSG_SIZE;
    msgh.msg_flags      = 0;

    st = recvmsg(sock, &msgh, 0);
    if(st < 0)
        return -1;

    *len = st;
    h = CMSG_FIRSTHDR(&msgh);
    /* Check if we received what we expected */
    if(h == NULL
            || h->cmsg_len    != CMSG_LEN(sizeof(int))
            || h->cmsg_level  != SOL_SOCKET
            || h->cmsg_type   != SCM_RIGHTS) {
        return -2;
    }
    fd = ((int *)CMSG_DATA(h))[0];
    if(fd < 0)
        return -3;
    return fd;
}
