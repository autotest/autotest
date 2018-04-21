"""
This module began as a more-or-less direct translation of jsonview.js from the
JSONView project, http://code.google.com/p/jsonview.  Here's the original
JSONView license:

---
MIT License

Copyright (c) 2009 Benjamin Hollis

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
---
"""

import simplejson

_HTML_DOCUMENT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<title>JSON output</title>
<link rel="stylesheet" type="text/css" href="/afe/server/static/jsonview.css">
</head>
<body>
<div id="json">
%s
</div>
</body>
</html>
"""


class JsonHtmlFormatter(object):

    def _html_encode(self, value):
        if value is None:
            return ''
        return (str(value).replace('&', '&amp;').replace('"', '&quot;')
                .replace('<', '&lt;').replace('>', '&gt;'))

    def _decorate_with_span(self, value, className):
        return '<span class="%s">%s</span>' % (
            className, self._html_encode(value))

    # Convert a basic JSON datatype (number, string, boolean, null, object,
    # array) into an HTML fragment.
    def _value_to_html(self, value):
        if value is None:
            return self._decorate_with_span('null', 'null')
        elif isinstance(value, list):
            return self._array_to_html(value)
        elif isinstance(value, dict):
            return self._object_to_html(value)
        elif isinstance(value, bool):
            return self._decorate_with_span(str(value).lower(), 'bool')
        elif isinstance(value, (int, float)):
            return self._decorate_with_span(value, 'num')
        else:
            assert isinstance(value, basestring)
            return self._decorate_with_span('"%s"' % value, 'string')

    # Convert an array into an HTML fragment
    def _array_to_html(self, array):
        if not array:
            return '[ ]'

        output = ['[<ul class="array collapsible">']
        for value in array:
            output.append('<li>')
            output.append(self._value_to_html(value))
            output.append('</li>')
        output.append('</ul>]')
        return ''.join(output)

    def _link_href(self, href):
        if '?' in href:
            joiner = '&amp;'
        else:
            joiner = '?'
        return href + joiner + 'alt=json-html'

    # Convert a JSON object to an HTML fragment
    def _object_to_html(self, json_object):
        if not json_object:
            return '{ }'

        output = ['{<ul class="obj collapsible">']
        for key, value in json_object.items():
            assert isinstance(key, basestring)
            output.append('<li>')
            output.append('<span class="prop">%s</span>: '
                          % self._html_encode(key))
            value_html = self._value_to_html(value)
            if key == 'href':
                assert isinstance(value, basestring)
                output.append('<a href="%s">%s</a>' % (self._link_href(value),
                                                       value_html))
            else:
                output.append(value_html)
            output.append('</li>')
        output.append('</ul>}')
        return ''.join(output)

    # Convert a whole JSON object into a formatted HTML document.
    def json_to_html(self, json_value):
        return _HTML_DOCUMENT_TEMPLATE % self._value_to_html(json_value)


class JsonToHtmlMiddleware(object):

    def process_response(self, request, response):
        if response['Content-type'] != 'application/json':
            return response
        if request.GET.get('alt', None) != 'json-html':
            return response

        json_value = simplejson.loads(response.content)
        html = JsonHtmlFormatter().json_to_html(json_value)
        response.content = html
        response['Content-type'] = 'text/html'
        response['Content-length'] = len(html)
        return response
