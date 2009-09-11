#!/usr/bin/python

import cgi, traceback, urllib2
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

result_dict = serviceHandler.ServiceHandler.blank_result_dict()
try:
    file_contents = urllib2.urlopen('http://localhost' + path).read()
    result_dict['result'] = file_contents
except urllib2.HTTPError:
    result_dict['err'] = LogFileNotFound('%s not found' % path)
    result_dict['err_traceback'] = traceback.format_exc()

encoded_result = serviceHandler.ServiceHandler.translateResult(result_dict)
print script % dict(callback=callback, result=encoded_result)
