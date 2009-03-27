#!/usr/bin/python

import cgi, urllib2
import common
from autotest_lib.frontend.afe.json_rpc import serviceHandler

script = """\
Content-Type: text/javascript

%(callback)s(%(result)s);
"""

class LogFileNotFound(Exception):
    pass

form = cgi.FieldStorage(keep_blank_values=True)
encoded_request = form['request'].value
callback = form['callback'].value

request = serviceHandler.ServiceHandler.translateRequest(encoded_request)
parameters = request['params'][0]
path = parameters['path']

result, error = None, None
try:
    file_contents = urllib2.urlopen('http://localhost' + path).read()
    result = file_contents
except urllib2.HTTPError:
    error = LogFileNotFound('%s not found' % path)

encoded_result = serviceHandler.ServiceHandler.translateResult(result, error,
                                                               None, None)
print script % dict(callback=callback, result=encoded_result)
