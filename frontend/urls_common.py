import os
from django.conf.urls import defaults


def generate_patterns(django_name, gwt_name):
    """
    Generates the common URL patterns for the given names

    @param django_name the full name of the Django application
                       (e.g., frontend.afe)
    @param gwt_name the name of the GWT project (e.g., AfeClient)
    @return the common standard and the debug pattern lists, as a tuple
    """

    pattern_list = defaults.patterns(
            django_name,
            (r'^(?:|noauth/)rpc/', 'views.handle_rpc'),
            (r'^rpc_doc', 'views.rpc_documentation'),
        )

    debug_pattern_list = defaults.patterns('',
            # for GWT hosted mode
            (r'^(?P<forward_addr>autotest.*)',
             'autotest_lib.frontend.afe.views.gwt_forward'),

            # for GWT compiled files
            (r'^client/(?P<path>.*)$', 'django.views.static.serve',
             {'document_root': os.path.join(os.path.dirname(__file__), '..',
                                            'frontend', 'client', 'www')}),
            # redirect / to compiled client
            (r'^$', 'django.views.generic.simple.redirect_to',
             {'url':
              'client/autotest.%(name)s/%(name)s.html' % dict(name=gwt_name)}),
        )

    return (pattern_list, debug_pattern_list)
