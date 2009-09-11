
"""
  Copyright (c) 2007 Jan-Klaas Kollhof

  This file is part of jsonrpc.

  jsonrpc is free software; you can redistribute it and/or modify
  it under the terms of the GNU Lesser General Public License as published by
  the Free Software Foundation; either version 2.1 of the License, or
  (at your option) any later version.

  This software is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU Lesser General Public License for more details.

  You should have received a copy of the GNU Lesser General Public License
  along with this software; if not, write to the Free Software
  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""

import traceback

from autotest_lib.frontend.afe.simplejson import decoder, encoder

def customConvertJson(value):
    """\
    Recursively process JSON values and do type conversions.
    -change floats to ints
    -change unicodes to strs
    """
    if isinstance(value, float):
        return int(value)
    elif isinstance(value, unicode):
        return str(value)
    elif isinstance(value, list):
        return [customConvertJson(item) for item in value]
    elif isinstance(value, dict):
        new_dict = {}
        for key, val in value.iteritems():
            new_key = customConvertJson(key)
            new_val = customConvertJson(val)
            new_dict[new_key] = new_val
        return new_dict
    else:
        return value

json_encoder = encoder.JSONEncoder()
json_decoder = decoder.JSONDecoder()


def ServiceMethod(fn):
    fn.IsServiceMethod = True
    return fn

class ServiceException(Exception):
    pass

class ServiceRequestNotTranslatable(ServiceException):
    pass

class BadServiceRequest(ServiceException):
    pass

class ServiceMethodNotFound(ServiceException):
    pass


class ServiceHandler(object):

    def __init__(self, service):
        self.service=service


    @classmethod
    def blank_result_dict(cls):
        return {'id': None, 'result': None, 'err': None, 'err_traceback': None}

    def dispatchRequest(self, request):
        """
        Invoke a json RPC call from a decoded json request.
        @param request: a decoded json_request
        @returns a dictionary with keys id, result, err and err_traceback
        """
        results = self.blank_result_dict()

        try:
            results['id'] = self._getRequestId(request)
            methName = request['method']
            args = request['params']
        except KeyError:
            raise BadServiceRequest(request)

        try:
            meth = self.findServiceEndpoint(methName)
            results['result'] = self.invokeServiceEndpoint(meth, args)
        except Exception, err:
            results['err_traceback'] = traceback.format_exc()
            results['err'] = err

        return results


    def _getRequestId(self, request):
        try:
            return request['id']
        except KeyError:
            raise BadServiceRequest(request)


    def handleRequest(self, jsonRequest):
        request = self.translateRequest(jsonRequest)
        results = self.dispatchRequest(request)
        return self.translateResult(results)


    @staticmethod
    def translateRequest(data):
        try:
            req = json_decoder.decode(data)
        except:
            raise ServiceRequestNotTranslatable(data)
        req = customConvertJson(req)
        return req

    def findServiceEndpoint(self, name):
        try:
            meth = getattr(self.service, name)
            return meth
        except AttributeError:
            raise ServiceMethodNotFound(name)

    def invokeServiceEndpoint(self, meth, args):
        return meth(*args)

    @staticmethod
    def translateResult(result_dict):
        """
        @param result_dict: a dictionary containing the result, error, traceback
                            and id.
        @returns translated json result
        """
        if result_dict['err'] is not None:
            error_name = result_dict['err'].__class__.__name__
            result_dict['err'] = {'name': error_name,
                                  'message': str(result_dict['err']),
                                  'traceback': result_dict['err_traceback']}
            result_dict['result'] = None

        try:
            json_dict = {'result': result_dict['result'],
                         'id': result_dict['id'],
                         'error': result_dict['err'] }
            data = json_encoder.encode(json_dict)
        except TypeError, e:
            err_traceback = traceback.format_exc()
            print err_traceback
            err = {"name" : "JSONEncodeException",
                   "message" : "Result Object Not Serializable",
                   "traceback" : err_traceback}
            data = json_encoder.encode({"result":None, "id":result_dict['id'],
                                        "error":err})

        return data
