#!/usr/bin/python
# Copyright 2009 Google Inc. Released under the GPL v2

import unittest, cStringIO, httplib

import common
from autotest_lib.mirror import source
from autotest_lib.client.common_lib.test_utils import mock


class rsync_source_unittest(unittest.TestCase):
    _cmd_template = '/usr/bin/rsync -rltz --no-motd %s %s/%s'
    _prefix = 'rsync://rsync.kernel.org/pub/linux/kernel'
    _path1 = 'v2.6/patch-2.6.*.bz2'
    _path2 = 'v2.6/testing/patch*.bz2'

    _output1 = """\
-rw-rw-r--       10727 2003/12/17 19:04:34 patch-2.6.0.bz2
-rw-rw-r--      777959 2004/01/08 23:31:48 patch-2.6.1.bz2
-rw-rw-r--     4851041 2004/12/24 14:38:58 patch-2.6.10.bz2
-rw-r--r--         713 2005/03/08 16:59:09 patch-2.6.11.1.bz2
-rw-r--r--       15141 2005/05/16 11:17:23 patch-2.6.11.10.bz2
-rw-rw-r--       20868 2005/05/26 22:51:21 patch-2.6.11.11.bz2
-rw-rw-r--       23413 2005/06/11 19:57:26 patch-2.6.11.12.bz2
-rw-r--r--        1010 2005/03/12 22:55:52 patch-2.6.11.2.bz2
"""
    _output2 = """\
-rw-rw-r--    10462721 2009/04/07 15:45:35 patch-2.6.30-rc1.bz2
-rw-rw-r--    10815919 2009/04/14 19:01:40 patch-2.6.30-rc2.bz2
-rw-rw-r--    11032734 2009/04/21 20:28:11 patch-2.6.30-rc3.bz2
"""
    _output_excluded = """\
-rw-rw-r--    10462721 2009/04/07 15:45:35 patch-2.6.30-rc1.bz2
-rw-rw-r--    11032734 2009/04/21 20:28:11 patch-2.6.30-rc3.bz2
"""
    _known_files = {
        'v2.6/patch-2.6.1.bz2': source.database.item(
            'v2.6/patch-2.6.1.bz2', 777959, 1073633508),
        'v2.6/patch-2.6.11.10.bz2': source.database.item(
            'v2.6/patch-2.6.11.10.bz2', 15141, 1116267443),
        'v2.6/testing/patch-2.6.30-rc1.bz2': source.database.item(
            'v2.6/testing/patch-2.6.30-rc1.bz2', 10462721, 1239144335),
        }
    _result = {
        'v2.6/patch-2.6.0.bz2': source.database.item(
            'v2.6/patch-2.6.0.bz2', 10727, 1071716674),
        'v2.6/patch-2.6.10.bz2': source.database.item(
            'v2.6/patch-2.6.10.bz2', 4851041, 1103927938),
        'v2.6/patch-2.6.11.12.bz2': source.database.item(
            'v2.6/patch-2.6.11.12.bz2', 23413, 1118545046),
        'v2.6/patch-2.6.11.11.bz2': source.database.item(
            'v2.6/patch-2.6.11.11.bz2', 20868, 1117173081),
        'v2.6/patch-2.6.11.2.bz2': source.database.item(
            'v2.6/patch-2.6.11.2.bz2', 1010, 1110696952),
        'v2.6/patch-2.6.11.1.bz2': source.database.item(
            'v2.6/patch-2.6.11.1.bz2', 713, 1110329949),
        'v2.6/testing/patch-2.6.30-rc3.bz2': source.database.item(
            'v2.6/testing/patch-2.6.30-rc3.bz2', 11032734, 1240370891),
        'v2.6/testing/patch-2.6.30-rc2.bz2': source.database.item(
            'v2.6/testing/patch-2.6.30-rc2.bz2', 10815919, 1239760900),
        }

    def setUp(self):
        self.god = mock.mock_god()
        self.db_mock = self.god.create_mock_class(
            source.database.database, 'database')
        self.god.stub_function(source.utils, 'system_output')


    def tearDown(self):
        self.god.unstub_all()


    def test_simple(self):
        # record
        (source.utils.system_output.expect_call(
            self._cmd_template % ('', self._prefix, self._path1))
            .and_return(self._output1))
        (source.utils.system_output.expect_call(
            self._cmd_template % ('', self._prefix, self._path2))
            .and_return(self._output2))
        self.db_mock.get_dictionary.expect_call().and_return(self._known_files)

        # playback
        s = source.rsync_source(self.db_mock, self._prefix)
        s.add_path('v2.6/patch-2.6.*.bz2', 'v2.6')
        s.add_path('v2.6/testing/patch*.bz2', 'v2.6/testing')
        self.assertEquals(s.get_new_files(), self._result)
        self.god.check_playback()


    def test_exclusions(self):
        # setup
        exclude_str = '--exclude "2.6.30-rc2"'
        excluded_result = dict(self._result)
        del excluded_result['v2.6/testing/patch-2.6.30-rc2.bz2']

        # record
        (source.utils.system_output.expect_call(
            self._cmd_template % (exclude_str, self._prefix, self._path1))
            .and_return(self._output1))
        (source.utils.system_output.expect_call(
            self._cmd_template % (exclude_str, self._prefix, self._path2))
            .and_return(self._output_excluded))
        self.db_mock.get_dictionary.expect_call().and_return(self._known_files)

        # playback
        s = source.rsync_source(self.db_mock, self._prefix,
                                excludes=('2.6.30-rc2',))
        s.add_path('v2.6/patch-2.6.*.bz2', 'v2.6')
        s.add_path('v2.6/testing/patch*.bz2', 'v2.6/testing')
        self.assertEquals(s.get_new_files(), excluded_result)
        self.god.check_playback()


class url_source_unittest(unittest.TestCase):
    _prefix = 'http://www.kernel.org/pub/linux/kernel/'

    _path1 = 'v2.6/'
    _full_path1 = '%s%s' % (_prefix, _path1)

    _path2 = 'v2.6/testing'
    _full_path2 = '%s%s/' % (_prefix, _path2)

    _output1 = """\
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
<html>
 <head>
  <title>Index of /pub/linux/kernel/v2.6</title>
 </head>
 <body>
<h1>Index of /pub/linux/kernel/v2.6</h1>
<pre><a href="?C=N;O=D">Name</a>                         <a href="?C=M;O=A">Last modified</a>      <a href="?C=S;O=A">Size</a>  <hr><a href="/pub/linux/kernel/">Parent Directory</a>                                  -
<a href="incr/">incr/</a>                        23-Mar-2009 22:13    -
<a href="pre-releases/">pre-releases/</a>                18-Dec-2003 15:50    -
<a href="snapshots/">snapshots/</a>                   25-Apr-2009 00:18    -
<a href="stable-review/">stable-review/</a>               23-Apr-2009 07:51    -
<a href="testing/">testing/</a>                     22-Apr-2009 03:31    -
<a href="ChangeLog-2.6.0">ChangeLog-2.6.0</a>              18-Dec-2003 03:04   12K
<a href="ChangeLog-2.6.1">ChangeLog-2.6.1</a>              09-Jan-2004 07:08  189K
<a href="ChangeLog-2.6.2">ChangeLog-2.6.2</a>              04-Feb-2004 04:06  286K
<a href="patch-2.6.19.6.bz2.sign">patch-2.6.19.6.bz2.sign</a>      03-Mar-2007 01:06  248
<a href="patch-2.6.19.6.gz">patch-2.6.19.6.gz</a>            03-Mar-2007 01:06   68K
<a href="patch-2.6.19.6.gz.sign">patch-2.6.19.6.gz.sign</a>       03-Mar-2007 01:06  248
<a href="patch-2.6.19.6.sign">patch-2.6.19.6.sign</a>          03-Mar-2007 01:06  248
<a href="patch-2.6.19.7.bz2">patch-2.6.19.7.bz2</a>           03-Mar-2007 05:29   62K
<a href="patch-2.6.19.7.bz2.sign">patch-2.6.19.7.bz2.sign</a>      03-Mar-2007 05:29  248
<a href="linux-2.6.28.1.tar.sign">linux-2.6.28.1.tar.sign</a>      18-Jan-2009 18:48  248
<a href="linux-2.6.28.2.tar.bz2">linux-2.6.28.2.tar.bz2</a>       25-Jan-2009 00:47   50M
<a href="linux-2.6.28.2.tar.bz2.sign">linux-2.6.28.2.tar.bz2.sign</a>  25-Jan-2009 00:47  248
<a href="linux-2.6.28.2.tar.gz">linux-2.6.28.2.tar.gz</a>        25-Jan-2009 00:47   64M
<a href="linux-2.6.28.2.tar.gz.sign">linux-2.6.28.2.tar.gz.sign</a>   25-Jan-2009 00:47  248
<a href="linux-2.6.28.2.tar.sign">linux-2.6.28.2.tar.sign</a>      25-Jan-2009 00:47  248
<a href="linux-2.6.28.3.tar.bz2">linux-2.6.28.3.tar.bz2</a>       02-Feb-2009 18:21   50M
<hr></pre>
</body></html>
"""
    _output2 = """\
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
<html>
 <head>
  <title>Index of /pub/linux/kernel/v2.6/testing</title>
 </head>
 <body>
<h1>Index of /pub/linux/kernel/v2.6/testing</h1>
<pre><a href="?C=N;O=D">Name</a>                          <a href="?C=M;O=A">Last modified</a>      <a href="?C=S;O=A">Size</a>  <hr><a href="/pub/linux/kernel/v2.6/">Parent Directory</a>                                   -
<a href="cset/">cset/</a>                         04-Apr-2005 17:12    -
<a href="incr/">incr/</a>                         22-Apr-2009 03:30    -
<a href="old/">old/</a>                          14-Jul-2003 16:06    -
<a href="v2.6.1/">v2.6.1/</a>                       15-Feb-2008 21:47    -
<a href="v2.6.2/">v2.6.2/</a>                       15-Feb-2008 21:47    -
<a href="LATEST-IS-2.6.30-rc3">LATEST-IS-2.6.30-rc3</a>          22-Apr-2009 03:13    0
<a href="linux-2.6.30-rc1.tar.bz2">linux-2.6.30-rc1.tar.bz2</a>      07-Apr-2009 22:43   57M
<a href="linux-2.6.30-rc1.tar.bz2.sign">linux-2.6.30-rc1.tar.bz2.sign</a> 07-Apr-2009 22:43  248
<a href="linux-2.6.30-rc3.tar.gz.sign">linux-2.6.30-rc3.tar.gz.sign</a>  22-Apr-2009 03:25  248
<a href="linux-2.6.30-rc3.tar.sign">linux-2.6.30-rc3.tar.sign</a>     22-Apr-2009 03:25  248
<a href="patch-2.6.30-rc1.bz2">patch-2.6.30-rc1.bz2</a>          07-Apr-2009 22:45   10M
<a href="patch-2.6.30-rc1.bz2.sign">patch-2.6.30-rc1.bz2.sign</a>     07-Apr-2009 22:45  248
<hr></pre>
</body></html>
"""
    _extracted_links1 = (
        (_full_path1 + 'patch-2.6.19.6.gz', '70021',
            (2007, 3, 3, 1, 6, 0, 0, 1, 0)),
        (_full_path1 + 'patch-2.6.19.7.bz2', '63424',
            (2007, 3, 3, 5, 29, 0, 0, 1, 0)),
        (_full_path1 + 'linux-2.6.28.2.tar.bz2', '52697313',
            (2009, 1, 25, 0, 47, 0, 0, 1, 0)),
        (_full_path1 + 'linux-2.6.28.2.tar.gz', '66781113',
            (2009, 1, 25, 0, 47, 0, 0, 1, 0)),
        (_full_path1 + 'linux-2.6.28.3.tar.bz2', '52703558',
            (2009, 2, 2, 18, 21, 0, 0, 1, 0)),
        )

    _extracted_links2 = (
        (_full_path2 + 'patch-2.6.30-rc1.bz2', '10462721',
            (2009, 4, 7, 22, 43, 0, 0, 1, 0)),
        )

    _known_files = {
        _full_path1 + 'linux-2.6.28.2.tar.gz': source.database.item(
            _full_path1 + 'linux-2.6.28.2.tar.gz', 66781113, 1232873220),
        }

    _result = {
        _full_path1 + 'linux-2.6.28.3.tar.bz2': source.database.item(
            _full_path1 + 'linux-2.6.28.3.tar.bz2', 52703558, 1233627660),
        _full_path2 + 'patch-2.6.30-rc1.bz2': source.database.item(
            _full_path2 + 'patch-2.6.30-rc1.bz2', 10462721, 1239172980),
        _full_path1 + 'patch-2.6.19.7.bz2': source.database.item(
            _full_path1 + 'patch-2.6.19.7.bz2', 63424, 1172928540),
        _full_path1 + 'linux-2.6.28.2.tar.bz2': source.database.item(
            _full_path1 + 'linux-2.6.28.2.tar.bz2', 52697313, 1232873220),
        _full_path1 + 'patch-2.6.19.6.gz': source.database.item(
            _full_path1 + 'patch-2.6.19.6.gz', 70021, 1172912760),
        }

    def setUp(self):
        self.god = mock.mock_god()
        self.db_mock = self.god.create_mock_class(
            source.database.database, 'database')
        self.god.stub_function(source.urllib2, 'urlopen')
        self.addinfourl_mock = self.god.create_mock_class(
            source.urllib2.addinfourl, 'addinfourl')
        self.mime_mock = self.god.create_mock_class(
            httplib.HTTPMessage, 'HTTPMessage')


    def tearDown(self):
        self.god.unstub_all()


    def test_get_new_files(self):
        # record
        (source.urllib2.urlopen.expect_call(self._full_path1)
            .and_return(cStringIO.StringIO(self._output1)))
        for link, size, time in self._extracted_links1:
            (source.urllib2.urlopen.expect_call(link)
                .and_return(self.addinfourl_mock))
            self.addinfourl_mock.info.expect_call().and_return(self.mime_mock)
            self.mime_mock.get.expect_call('content-length').and_return(size)
            self.mime_mock.getdate.expect_call('date').and_return(time)

        (source.urllib2.urlopen.expect_call(self._full_path2)
            .and_return(cStringIO.StringIO(self._output2)))
        for link, size, time in self._extracted_links2:
            (source.urllib2.urlopen.expect_call(link)
                .and_return(self.addinfourl_mock))
            self.addinfourl_mock.info.expect_call().and_return(self.mime_mock)
            self.mime_mock.get.expect_call('content-length').and_return(size)
            self.mime_mock.getdate.expect_call('date').and_return(time)

        self.db_mock.get_dictionary.expect_call().and_return(self._known_files)

        # playback
        s = source.url_source(self.db_mock, self._prefix)
        s.add_url(self._path1, r'.*\.(gz|bz2)$')
        s.add_url(self._path2, r'.*patch-[0-9.]+(-rc[0-9]+)?\.bz2$')
        self.assertEquals(s.get_new_files(), self._result)
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
