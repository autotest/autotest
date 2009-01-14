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
    # escape backslashes, double-quotes, newlines, and carriage returns -- all
    # would mess up a Javascript string literal
    escaped_contents = file_contents.replace(
        '\\', r'\\').replace(
        '"', r'\"').replace(
        '\n', r'\n').replace(
        '\r', r'\r')
    result = '{"contents" : "%s"}' % escaped_contents
except urllib2.HTTPError:
    result = '{"error" : "File not found"}'

print script % dict(callback=callback, result=result)
