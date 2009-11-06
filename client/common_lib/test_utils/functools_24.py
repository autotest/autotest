#
# Copyright (c) 2005 Dima Dorfman.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

__all__ = ['compose', 'fastcut']
__revision__ = '$Dima: pylib/functools/functools.py,v 1.2 2005/08/22 07:05:22 dima Exp $'


def compose(*args):

    if len(args) < 1:
        raise TypeError, 'compose expects at least one argument'
    fs = args[-2::-1]
    g = args[-1]

    def composecall(*args, **kw):
        res = g(*args, **kw)
        for f in fs:
            res = f(res)
        return res

    return composecall


def fastcut(*sargs, **skw):
    try:
        fun = sargs[0]
    except IndexError:
        raise TypeError, 'fastcut requires at least one argument'
    sargs = sargs[1:]

    def fastcutcall(*args, **kw):
        rkw = skw.copy()
        rkw.update(kw)
        return fun(*(sargs + args), **rkw)

    return fastcutcall


for x in __all__:
    globals()['py_%s' % x] = globals()[x]
del x

try:
    import _functools
except ImportError:
    pass
else:
    for x in __all__:
        globals()['c_%s' % x] = globals()[x] = getattr(_functools, x)
    del x
