from django.conf.urls.defaults import *
from django.conf import settings
import os

pattern_list = [(r'^(?:|noauth/)rpc/', 'new_tko.tko.views.handle_rpc'),
                (r'^(?:|noauth/)jsonp_rpc/',
                 'new_tko.tko.views.handle_jsonp_rpc'),
                (r'^(?:|noauth/)csv/', 'new_tko.tko.views.handle_csv'),
                (r'^rpc_doc', 'new_tko.tko.views.rpc_documentation'),
                (r'^(?:|noauth/)plot/', 'new_tko.tko.views.handle_plot')]

debug_pattern_list = [
    (r'^model_doc/', 'new_tko.tko.views.model_documentation'),

    # for GWT hosted mode
    (r'^(?P<forward_addr>autotest.*)',
     'autotest_lib.frontend.afe.views.gwt_forward'),

    # for GWT compiled files
    (r'^client/(?P<path>.*)$', 'django.views.static.serve',
     {'document_root': os.path.join(os.path.dirname(__file__), '..', '..',
                                    'frontend', 'client', 'www')}),
    # redirect / to compiled client
    (r'^$', 'django.views.generic.simple.redirect_to',
     {'url': 'client/autotest.TkoClient/TkoClient.html'}),

]

if settings.DEBUG:
    pattern_list += debug_pattern_list

urlpatterns = patterns('', *pattern_list)
