#!/usr/bin/python

import cgi, urllib2

script = """\
Content-Type: text/javascript

%(callback)s(%(result)s);
"""

form = cgi.FieldStorage()
path = form['path'].value
callback = form['callback'].value

try:
    file_contents = urllib2.urlopen('http://localhost' + path).read()
    escaped_contents = file_contents.replace(
        '\\', '\\\\').replace( # get rid of backslashes
        '"', r'\"').replace( # escape quotes
        '\n', '\\n') # escape newlines
    result = '{"contents" : "%s"}' % escaped_contents
except urllib2.HTTPError:
    result = '{"error" : "File not found"}'

print script % dict(callback=callback, result=result)
