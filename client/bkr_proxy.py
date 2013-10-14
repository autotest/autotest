# bkr_proxy.py
#
# Copyright (C) 2011 Jan Stancek <jstancek@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# Started by Jan Stancek <jstancek@redhat.com> 2011
"""
bkr_proxy - class used to talk to beaker
"""
__author__ = """Don Zickus 2013"""


import time
import os
import logging
import re
import urllib
import urllib2
from autotest.client.shared import utils

log = logging


AUTOTEST_CACHE_DIR = '/var/cache/autotest'


class BkrProxyException(Exception):

    def __init__(self, text):
        Exception.__init__(self, text)

'''Hard coded internal paths'''


def make_path_cmdlog(r):
    """
    Converts a recipe id into an internal path for logging purposes

    :param r: recipe id

    :return: a path to the internal command log
    """

    path = AUTOTEST_CACHE_DIR + '/recipes/' + r
    if not os.path.exists(path):
        os.makedirs(path)
    if not os.path.isdir(path):
        raise BkrProxyException("Path(%s) exists and is not a directory" % path)
    return path + '/cmd_log'


def make_path_bkrcache(r):
    """
    Converts a recipe id into an internal path for cache'ing recipe

    :param r: recipe id

    :return: a path to the internal recipe cache file
    """

    return AUTOTEST_CACHE_DIR + '/recipes/' + r + '/beaker_recipe.cache'

'''End Hard coded internal paths'''

"""
Hard coded paths as described in the Beaker Server API
http://beaker-project.org/dev/proposals/harness-api.html
"""


def make_path_recipe(r):
    """
    Converts a recipe id into a beaker path

    :param r: recipe id

    :return: a beaker path to the recipe id
    """

    return '/recipes/' + r


def make_path_watchdog(r):
    """
    Converts a recipe id into a beaker path for the watchdog

    :param r: recipe id

    :return: a beaker path of the recipe's watchdog file
    """

    return '/recipes/' + r + '/watchdog'


def make_path_status(r, t=None):
    """
    Converts id into a beaker path to status file

    Given a recipe id and/or a task id, translate them into
    the proper beaker path to the status file.  Recipe only, returns
    the path to the recipe's status, whereas including a task returns
    the path to the task's status.

    :param r: recipe id
    :param t: task id

    :return: a beaker path of the recipe's/task's status file
    """

    rpath = '/recipes/' + r
    tpath = t and '/tasks/' + t or ''

    return rpath + tpath + '/status'


def make_path_result(r, t):
    """
    Converts task id into a beaker path to result file

    Given a recipe id and a task id, translate them into
    the proper beaker path to the result file.

    :param r: recipe id
    :param t: task id

    :return: a beaker path of the task's result file
    """

    rpath = '/recipes/' + r
    tpath = '/tasks/' + t

    return rpath + tpath + '/results/'


def make_path_log(r, t=None, i=None):
    """
    Converts id into a beaker path to log file

    Given a recipe id, a task id, and/or result id, translate
    them into the proper beaker path to the log file.  Depending
    on which log file is needed, provide the appropriate params.
    Note the dependency, a result id needs a task id and recipe id,
    while a task id needs a recipe id.

    :param r: recipe id
    :param t: task id
    :param i: result id

    :return: a beaker path of the task's result file
    """

    rpath = '/recipes/' + r
    tpath = t and '/tasks/' + t or ''
    ipath = i and '/results/' + i or ''

    return rpath + tpath + ipath + '/logs'

'''End Hard coded paths'''


def copy_remote(data, dest, use_put=None):
    """
    Copy data to a remote server using http calls POST or PUT

    Using http POST and PUT methods, copy data over http.  To use
    PUT method, provide a dictionary of values to be populated in
    the Content-Range and Content-Length headers.  Otherwise default
    is to use POST method.

    Traps on HTTPError 500 and 400

    :param data: encoded data string to copy remotely
    :param dest: remote server URL
    :param use_put: dictionary of items if using PUT method

    :return: html header info for post processing
    """

    ret = None
    req = urllib2.Request(dest, data=data)
    if use_put:
        req.add_header('Content-Type', 'application/octet-stream')
        end = use_put['start'] + use_put['size'] - 1
        req.add_header('Content-Range', 'bytes %s-%s/%s' % (use_put['start'],
                                                            end, use_put['total']))
        req.add_header('Content-Length', '%s' % use_put['size'])
        req.get_method = lambda: 'PUT'

    try:
        res = utils.urlopen(req)
        ret = res.info()
        res.close()
    except urllib2.HTTPError, e:
        if e.code == 500:
            # the server aborted this recipe DIE DIE DIE
            raise BkrProxyException("We have been aborted!!!")
        elif e.code == 400 and use_put:
            log.error("Error(%s) failed to upload file %s" % (e.code, dest))
    return ret


def copy_local(data, dest, use_put=None):
    """
    Copy data locally to a file

    To aid in debugging, copy a file locally to verify the contents.
    Attempts to write the same data that would otherwise be sent
    remotely.

    :param data: encoded data string to copy locally
    :param dest: local file path
    :param use_put: chooses to write in binary or text

    :return: nothing
    """

    dpath = os.path.dirname(dest)
    if not os.path.isdir(dpath):
        os.makedirs(dpath)
    if use_put:
        open(dest, 'ab').write(data)
    else:
        open(dest, 'a').write("%s %s\n" % (time.time(), data))


def copy_data(data, dest, header=None, use_put=None):
    """
    Copy data to a destination

    To aid in debugging, copy a file locally to verify the contents.
    Attempts to write the same data that would otherwise be sent
    remotely.

    :param data: data string to copy
    :param dest: destination path
    :param header: header info item to return
    :param use_put: dictionary of items for PUT method

    :return: nothing or header info if requested
    """

    ret = None

    # PUT uses a filename instead of a list like POST
    if use_put:
        udata = data
    else:
        udata = urllib.urlencode(data)

    if utils.is_url(dest):
        ret = copy_remote(udata, dest, use_put)
        if header:
            return ret[header]
    else:
        if header:
            ret = dest + str(time.time())  # should be unique
            dest = ret + "/_task_result"
        copy_local(udata, dest, use_put)

    return ret


class BkrProxy(object):

    def __init__(self, recipe_id, labc_url=None):

        # labc_url determines local or remote functionality
        self.labc_url = labc_url or AUTOTEST_CACHE_DIR
        self.recipe_id = recipe_id

        if not labc_url:
            path = self.labc_url + make_path_recipe(self.recipe_id)
            log.info('Writing offline files to %s' % path)

        path = make_path_cmdlog(self.recipe_id)
        self.cmd_log = open(path, 'a', 0)

    def _upload_file(self, lf, rp, r, t=None, i=None):
        if not os.path.isfile(lf):
            raise BkrProxyException("Bad file - %s" % lf)

        lfile = os.path.basename(lf)
        path = self.labc_url + make_path_log(r, t, i) + rp + '/' + lfile

        #copy in chunks
        chunksize = 262144
        start = 0
        total = os.path.getsize(lf)
        use_put = {'total': total}
        f = open(lf, 'r')

        def readchunk():
            return f.read(chunksize)

        for d in iter(readchunk, ''):
            use_put['start'] = start
            use_put['size'] = len(d)
            copy_data(d, path, use_put=use_put)
            start += len(d)

        if total == 0:
            use_put['start'] = 0
            use_put['size'] = 0
            copy_data('', path, use_put=use_put)
        f.close()

    def recipe_upload_file(self, localfile, remotepath=''):
        self.cmd_log.write('recipe_upload_file: localfile=%s, remotepath=%s\n' %
                           (localfile, remotepath))

        self._upload_file(localfile, remotepath, self.recipe_id)

    def task_upload_file(self, task_id, localfile, remotepath=''):
        self.cmd_log.write('task_upload_file: task_id(%s) localfile=%s, remotepath=%s\n' %
                           (task_id, localfile, remotepath))

        self._upload_file(localfile, remotepath, self.recipe_id, task_id)

    def result_upload_file(self, task_id, result_id, localfile, remotepath=''):
        self.cmd_log.write('result_upload_file: task_id(%s), result_id(%s)'
                           ' localfile=%s, remotepath=%s\n' %
                           (task_id, result_id, localfile, remotepath))

        self._upload_file(localfile, remotepath, self.recipe_id, task_id, result_id)

    def get_recipe(self):
        self.cmd_log.write('get_recipe: GET %s\n' % self.recipe_id)

        path = make_path_bkrcache(self.recipe_id)
        try:
            rpath = self.labc_url + make_path_recipe(self.recipe_id)
            utils.get_file(rpath, path)
        except:
            # local will fall through to here
            if not os.path.isfile(path):
                raise BkrProxyException("No remote or cached recipe %s" % self.recipe_id)
        return open(path, 'r').read()

    def task_result(self, task_id, result_type, result_path,
                    result_score, result_summary):
        self.cmd_log.write('task_result: task_id(%s) result: %s, score: %s, summary: %s\n'
                           'path: %s\n' % (task_id, result_type, result_score, result_summary,
                                           result_path))

        data = {'result': result_type, 'path': result_path,
                'score': result_score, 'message': result_summary}

        path = self.labc_url + make_path_result(self.recipe_id, task_id)
        ret = copy_data(data, path, header='Location')

        # strip the path and return just the id
        return re.sub(path, "", ret)

    def task_start(self, task_id, kill_time=0):
        self.cmd_log.write('task_start: task_id(%s) kill_time(%s) RUNNING\n' % (task_id, kill_time))

        data = {'status': 'Running'}

        self.update_watchdog(task_id, kill_time)

        path = self.labc_url + make_path_status(self.recipe_id, task_id)
        copy_data(data, path)

    def task_stop(self, task_id):
        self.cmd_log.write('task_stop: task_id(%s) COMPLETED\n' % task_id)

        data = {'status': 'Completed'}

        path = self.labc_url + make_path_status(self.recipe_id, task_id)
        copy_data(data, path)

    def task_abort(self, task_id):
        self.cmd_log.write('task_abort: task_id(%s) ABORTED\n' % task_id)

        data = {'status': 'Aborted'}

        path = self.labc_url + make_path_status(self.recipe_id, task_id)
        copy_data(data, path)

    def recipe_stop(self):
        self.cmd_log.write('recipe_stop: recipe_id(%s) COMPLETED\n' % self.recipe_id)

        data = {'status': 'Completed'}

        path = self.labc_url + make_path_status(self.recipe_id)
        copy_data(data, path)

    def recipe_abort(self):
        self.cmd_log.write('recipe_abort: recipe_id(%s) ABORTED\n' % self.recipe_id)

        data = {'status': 'Aborted'}

        path = self.labc_url + make_path_status(self.recipe_id)
        copy_data(data, path)

    def update_watchdog(self, task_id, kill_time):
        self.cmd_log.write('update_watchdog: task_id(%s) killtime(%s)\n' % (task_id, kill_time))

        data = {'seconds': kill_time}

        if not kill_time or kill_time == 0:
            return

        if kill_time < 0:
            raise BkrProxyException("Illegal kill time - %s" % kill_time)

        path = self.labc_url + make_path_watchdog(self.recipe_id)
        copy_data(data, path)


if __name__ == '__main__':
    pass
