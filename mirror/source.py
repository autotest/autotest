# Copyright 2009 Google Inc. Released under the GPL v2

import re, time, urllib2, urlparse, HTMLParser

from autotest_lib.mirror import database
from autotest_lib.client.common_lib import utils


class source(object):
    """
    Abstract Base Class for the source classes.
    """
    def __init__(self, database):
        self.database = database


    def _get_new_files(self, files):
        """
        Return a copy of "files" after filtering out known old files
        from "files".
        """
        old_files = self.database.get_dictionary()
        return dict(filter(lambda x: x[0] not in old_files, files.iteritems()))


    def get_new_files(self):
        raise NotImplemented('get_new_files not implemented')


    def store_files(self, files):
        self.database.merge_dictionary(files)


class rsync_source(source):
    _cmd_template = '/usr/bin/rsync -rltz --no-motd %s %s/%s'

    def __init__(self, database, prefix, excludes = []):
        super(rsync_source, self).__init__(database)

        self.prefix = prefix
        self.exclude = ' '.join(['--exclude "' + x + '"' for x in excludes])
        self.sources = []


    def _parse_output(self, output, prefix):
        """
        Parse rsync's "ls -l" style output and return a dictionary of
        database.item indexed by the "name" field.
        """
        regex = re.compile(
            '-[rwx-]{9} +(\d+) (\d{4}/\d\d/\d\d \d\d:\d\d:\d\d) (.*)')
        res = {}
        for line in output.splitlines():
            match = regex.match(line)
            if match:
                groups = match.groups()
                timestamp = time.mktime(time.strptime(groups[1],
                                        '%Y/%m/%d %H:%M:%S'))
                if prefix:
                    fname = '%s/%s' % (prefix, groups[2])
                else:
                    fname = groups[2]

                item = database.item(fname, int(groups[0]), int(timestamp))
                res[item.name] = item

        return res


    def add_path(self, src, prefix=''):
        """
        Add paths to synchronize from the source.
        """
        self.sources.append((src, prefix))


    def get_new_files(self):
        """
        Implement source.get_new_files by using rsync listing feature.
        """
        files = {}
        for src, prefix in self.sources:
            output = utils.system_output(self._cmd_template %
                (self.exclude, self.prefix, src))
            files.update(self._parse_output(output, prefix))

        return self._get_new_files(files)


class _ahref_parser(HTMLParser.HTMLParser):
    def reset(self, url=None, pattern=None):
        HTMLParser.HTMLParser.reset(self)
        self.url = url
        self.pattern = pattern
        self.links = []


    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for name, value in attrs:
                if name == 'href':
                    # compose absolute URL if relative "href" found
                    url = urlparse.urljoin(self.url, value)
                    if self.pattern.match(url):
                        self.links.append(url)


    def get_ahref_list(self, url, pattern):
        self.reset(url, pattern)
        self.feed(urllib2.urlopen(url).read())
        self.close()

        return self.links


class url_source(source):
    """
    A simple URL based source that parses HTML to find references to
    kernel files.
    """
    _extension_pattern = re.compile(r'.*\.[^/.]+$')

    def __init__(self, database, prefix):
        super(url_source, self).__init__(database)
        self.prefix = prefix
        self.urls = []


    def add_url(self, url, pattern):
        """
        Add a URL path to a HTML document with links to kernel files.

        @param url: URL path to a HTML file with links to kernel files
                (can be either an absolute URL or one relative to self.prefix)
        @param pattern: regex pattern to filter kernel files links out of
                all othe links found in the HTML document
        """
        # if it does not have an extension then it's a directory and it needs
        # a trailing '/'. NOTE: there are some false positives such as
        # directories named "v2.6" where ".6" will be assumed to be extension.
        # In order for these to work the caller must provide a trailing /
        if url[-1:] != '/' and not self._extension_pattern.match(url):
            url = url + '/'
        self.urls.append((url, re.compile(pattern)))


    @staticmethod
    def _get_item(url):
        """
        Get a database.item object by fetching relevant HTTP information
        from the document pointed to by the given url.
        """
        try:
            info = urllib2.urlopen(url).info()
        except IOError, err:
            # file is referenced but does not exist
            print 'WARNING: %s' % err
            return None

        size = info.get('content-length')
        if size:
            size = int(size)
        else:
            size = -1

        timestamp = int(time.mktime(info.getdate('date')))
        if not timestamp:
            timestamp = 0

        return database.item(url, size, timestamp)


    def get_new_files(self):
        parser = _ahref_parser()

        files = {}
        for url, pattern in self.urls:
            links = parser.get_ahref_list(urlparse.urljoin(self.prefix, url),
                                          pattern)
            for link in links:
                item = self._get_item(link)
                if item:
                    files[item.name] = item

        return self._get_new_files(files)
