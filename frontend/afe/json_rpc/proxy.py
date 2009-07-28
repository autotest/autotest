
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

import urllib2
from autotest_lib.frontend.afe.simplejson import decoder, encoder
json_encoder = encoder.JSONEncoder()
json_decoder = decoder.JSONDecoder()

class JSONRPCException(Exception):
    pass

class ServiceProxy(object):
    def __init__(self, serviceURL, serviceName=None, headers=None):
        self.__serviceURL = serviceURL
        self.__serviceName = serviceName
        self.__headers = headers or {}

    def __getattr__(self, name):
        if self.__serviceName is not None:
            name = "%s.%s" % (self.__serviceName, name)
        return ServiceProxy(self.__serviceURL, name, self.__headers)

    def __call__(self, *args, **kwargs):
        postdata = json_encoder.encode({"method": self.__serviceName,
                                        'params': args + (kwargs,),
                                        'id':'jsonrpc'})
        request = urllib2.Request(self.__serviceURL, data=postdata,
                                  headers=self.__headers)
        respdata = urllib2.urlopen(request).read()
        try:
            resp = json_decoder.decode(respdata)
        except ValueError:
            raise JSONRPCException('Error decoding JSON reponse:\n' + respdata)
        if resp['error'] is not None:
            error_message = (resp['error']['name'] + ': ' +
                             resp['error']['message'] + '\n' +
                             resp['error']['traceback'])
            raise JSONRPCException(error_message)
        else:
            return resp['result']
