
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

from frontend.afe.simplejson import decoder, encoder

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

    def handleRequest(self, json):
        err=None
        err_traceback = None
        result = None
        id_=''

        #print 'Request:', json

        try:
            req = self.translateRequest(json)
        except ServiceRequestNotTranslatable, e:
            err = e
            req={'id':id_}

        if err==None:
            try:
                id_ = req['id']
                methName = req['method']
                args = req['params']
            except:
                err = BadServiceRequest(json)

        if err is None:
            try:
                meth = self.findServiceEndpoint(methName)
            except Exception, e:
                err_traceback = traceback.format_exc()
                print err_traceback
                err = e

        if err is None:
            try:
                result = self.invokeServiceEndpoint(meth, args)
            except Exception, e:
                err_traceback = traceback.format_exc()
                print err_traceback
                err = e
        resultdata = self.translateResult(result, err, err_traceback, id_)

        return resultdata

    @staticmethod
    def translateRequest(data):
        try:
            req = json_decoder.decode(data)
        except:
            raise ServiceRequestNotTranslatable(data)
        req = customConvertJson(req) # -srh
        return req

    def findServiceEndpoint(self, name):
        try:
            meth = getattr(self.service, name)
# -srh
#            if getattr(meth, "IsServiceMethod"):
            return meth
#            else:
#                raise ServiceMethodNotFound(name)
        except AttributeError:
            raise ServiceMethodNotFound(name)

    def invokeServiceEndpoint(self, meth, args):
        return meth(*args)

    @staticmethod
    def translateResult(rslt, err, err_traceback, id_):
        if err is not None:
            err = {"name": err.__class__.__name__, "message":str(err),
                   "traceback": err_traceback}
            rslt = None

        try:
            data = json_encoder.encode({"result":rslt,"id":id_,"error":err})
        except TypeError, e:
            err_traceback = traceback.format_exc()
            print err_traceback
            err = {"name" : "JSONEncodeException",
                   "message" : "Result Object Not Serializable",
                   "traceback" : err_traceback}
            data = json_encoder.encode({"result":None, "id":id_,"error":err})

        return data
