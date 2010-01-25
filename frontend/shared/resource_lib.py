import cgi, datetime, time, urllib
from django import http
from django.core import exceptions, urlresolvers
from django.utils import simplejson
from autotest_lib.frontend.shared import exceptions, query_lib
from autotest_lib.frontend.afe import model_logic


_JSON_CONTENT_TYPE = 'application/json'


def _resolve_class_path(class_path):
    module_path, class_name = class_path.rsplit('.', 1)
    module = __import__(module_path, {}, {}, [''])
    return getattr(module, class_name)


_NO_VALUE_SPECIFIED = object()

class _InputDict(dict):
    def get(self, key, default=_NO_VALUE_SPECIFIED):
        return super(_InputDict, self).get(key, default)


    @classmethod
    def remove_unspecified_fields(cls, field_dict):
        return dict((key, value) for key, value in field_dict.iteritems()
                    if value is not _NO_VALUE_SPECIFIED)


class Resource(object):
    _permitted_methods = None # subclasses must override this


    def __init__(self):
        assert self._permitted_methods


    @classmethod
    def dispatch_request(cls, request, *args, **kwargs):
        # handle a request directly
        try:
            instance = cls.from_uri_args(*args, **kwargs)
        except exceptions.ObjectDoesNotExist, exc:
            raise http.Http404(exc)
        return instance.handle_request(request)


    def handle_request(self, request):
        if request.method.upper() not in self._permitted_methods:
            return http.HttpResponseNotAllowed(self._permitted_methods)

        handler = getattr(self, request.method.lower())
        try:
            return handler(request)
        except exceptions.RequestError, exc:
            return exc.response


    # the handler methods below only need to be overridden if the resource
    # supports the method

    def get(self, request):
        """Handle a GET request.

        @returns an HttpResponse
        """
        raise NotImplementedError


    def post(self, request):
        """Handle a POST request.

        @returns an HttpResponse
        """
        raise NotImplementedError


    def put(self, request):
        """Handle a PUT request.

        @returns an HttpResponse
        """
        raise NotImplementedError


    def delete(self, request):
        """Handle a DELETE request.

        @returns an HttpResponse
        """
        raise NotImplementedError


    @classmethod
    def from_uri_args(cls):
        """Construct an instance from URI args.

        Default implementation for resources with no URI args.
        """
        return cls()


    def _uri_args(self):
        """Return (args, kwargs) for a URI reference to this resource.

        Default implementation for resources with no URI args.
        """
        return (), {}


    def _query_parameters(self):
        """Return sequence of tuples (name, description) for query parameters.

        Documents the available query parameters for GETting this resource.
        Default implementation for resources with no parameters.
        """
        return ()


    def href(self):
        """Return URI to this resource."""
        args, kwargs = self._uri_args()
        return urlresolvers.reverse(self.dispatch_request, args=args,
                                    kwargs=kwargs)


    @classmethod
    def resolve_uri(cls, uri):
        view_method, args, kwargs = urlresolvers.resolve(uri)
        resource_class = view_method.im_self # class owning this classmethod
        return resource_class.from_uri_args(*args, **kwargs)


    @classmethod
    def resolve_link(cls, link):
        if isinstance(link, dict):
            uri = link['href']
        elif isinstance(link, basestring):
            uri = link
        else:
            raise exceptions.BadRequest('Unable to understand link %s' % link)
        return cls.resolve_uri(uri)


    def link(self):
        return {'href': self.href()}


    def _query_parameters_response(self):
        return dict((name, description)
                    for name, description in self._query_parameters())


    def _basic_response(self, content):
        """Construct and return a simple 200 response."""
        assert isinstance(content, dict)
        query_parameters = self._query_parameters_response()
        if query_parameters:
            content['query_parameters'] = query_parameters
        encoded_content = simplejson.dumps(content)
        return http.HttpResponse(encoded_content,
                                 content_type=_JSON_CONTENT_TYPE)


    @classmethod
    def _decoded_input(cls, request):
        content_type = request.META.get('CONTENT_TYPE', _JSON_CONTENT_TYPE)
        raw_data = request.raw_post_data
        if content_type == _JSON_CONTENT_TYPE:
            try:
                raw_dict = simplejson.loads(raw_data)
            except ValueError, exc:
                raise exceptions.BadRequest('Error decoding request body: '
                                            '%s\n%r' % (exc, raw_data))
        elif content_type == 'application/x-www-form-urlencoded':
            cgi_dict = cgi.parse_qs(raw_data) # django won't do this for PUT
            raw_dict = {}
            for key, values in cgi_dict.items():
                value = values[-1] # take last value if multiple were given
                try:
                    # attempt to parse numbers, booleans and nulls
                    raw_dict[key] = simplejson.loads(value)
                except ValueError:
                    # otherwise, leave it as a string
                    raw_dict[key] = value
        else:
            raise exceptions.RequestError(415, 'Unsupported media type: %s'
                                          % content_type)

        return _InputDict(raw_dict)


    def _format_datetime(self, date_time):
        """Return ISO 8601 string for the given datetime"""
        if date_time is None:
            return None
        timezone_hrs = time.timezone / 60 / 60  # convert seconds to hours
        if timezone_hrs >= 0:
            timezone_join = '+'
        else:
            timezone_join = '' # minus sign comes from number itself
        timezone_spec = '%s%s:00' % (timezone_join, timezone_hrs)
        return date_time.strftime('%Y-%m-%dT%H:%M:%S') + timezone_spec


    @classmethod
    def _check_for_required_fields(cls, input_dict, fields):
        assert isinstance(fields, (list, tuple)), fields
        missing_fields = ', '.join(field for field in fields
                                   if field not in input_dict)
        if missing_fields:
            raise exceptions.BadRequest('Missing input: ' + missing_fields)


class Entry(Resource):
    class NullEntry(object):
        def link(self):
            return None


        def short_representation(self):
            return None

    _null_entry = NullEntry()


    _permitted_methods = ('GET', 'PUT', 'DELETE')


    # sublcasses must define this class to support querying
    QueryProcessor = query_lib.BaseQueryProcessor


    def __init__(self, instance):
        super(Entry, self).__init__()
        self.instance = instance


    @classmethod
    def from_optional_instance(cls, instance):
        if instance is None:
            return cls._null_entry
        return cls(instance)


    def short_representation(self):
        return self.link()


    def full_representation(self):
        return self.short_representation()


    def get(self, request):
        return self._basic_response(self.full_representation())


    def put(self, request):
        try:
            self.update(self._decoded_input(request))
        except model_logic.ValidationError, exc:
            raise exceptions.BadRequest('Invalid input: %s' % exc)
        return self._basic_response(self.full_representation())


    def delete(self, request):
        self.instance.delete()
        return http.HttpResponse(status=204) # No content


    def create_instance(self, input_dict, containing_collection):
        raise NotImplementedError


    def update(self, input_dict):
        raise NotImplementedError


class Collection(Resource):
    _DEFAULT_ITEMS_PER_PAGE = 50

    _permitted_methods=('GET', 'POST')

    # subclasses must override these
    queryset = None # or override _fresh_queryset() directly
    entry_class = None


    def __init__(self):
        super(Collection, self).__init__()
        assert self.entry_class is not None
        if isinstance(self.entry_class, basestring):
            type(self).entry_class = _resolve_class_path(self.entry_class)

        self._query_processor = self.entry_class.QueryProcessor()


    def _fresh_queryset(self):
        assert self.queryset is not None
        # always copy the queryset before using it to avoid caching
        return self.queryset.all()


    def _representation(self, entry_instances):
        members = []
        for instance in entry_instances:
            entry = self.entry_class(instance)
            members.append(entry.short_representation())

        rep = self.link()
        rep.update({'members': members})
        return rep


    def _read_int_parameter(self, query_dict, name, default):
        if name not in query_dict:
            return default
        input_value = query_dict[name]
        try:
            return int(input_value)
        except ValueError:
            raise exceptions.BadRequest('Invalid non-numeric value for %s: %r'
                                        % (name, input_value))


    def _apply_form_query(self, request, queryset):
        """Apply any query selectors passed as form variables."""
        for parameter, values in request.GET.lists():
            if not self._query_processor.has_selector(parameter):
                continue
            for value in values: # forms keys can have multiple values
                queryset = self._query_processor.apply_selector(queryset,
                                                                parameter,
                                                                value)
        return queryset


    def _filtered_queryset(self, request):
        return self._apply_form_query(request, self._fresh_queryset())


    def get(self, request):
        queryset = self._filtered_queryset(request)

        items_per_page = self._read_int_parameter(request.GET, 'items_per_page',
                                                  self._DEFAULT_ITEMS_PER_PAGE)
        start_index = self._read_int_parameter(request.GET, 'start_index', 0)
        page = queryset[start_index:(start_index + items_per_page)]

        rep = self._representation(page)
        selector_dict = dict((selector.name, selector.doc)
                             for selector
                             in self.entry_class.QueryProcessor.selectors())
        rep.update({'total_results': len(queryset),
                    'start_index': start_index,
                    'items_per_page': items_per_page,
                    'filtering_selectors': selector_dict})
        return self._basic_response(rep)


    def full_representation(self):
        # careful, this rep can be huge for large collections
        return self._representation(self._fresh_queryset())


    def post(self, request):
        input_dict = self._decoded_input(request)
        try:
            instance = self.entry_class.create_instance(input_dict, self)
            entry = self.entry_class(instance)
            entry.update(input_dict)
        except model_logic.ValidationError, exc:
            raise exceptions.BadRequest('Invalid input: %s' % exc)
        # RFC 2616 specifies that we provide the new URI in both the Location
        # header and the body
        response = http.HttpResponse(status=201, # Created
                                     content=entry.href())
        response['Location'] = entry.href()
        return response


class Relationship(Collection):
    _permitted_methods=('GET', 'PUT')

    base_entry_class = None # subclasses must override this


    def __init__(self, base_entry):
        assert self.base_entry_class
        if isinstance(self.base_entry_class, basestring):
            type(self).base_entry_class = _resolve_class_path(
                    self.base_entry_class)
        assert isinstance(base_entry, self.base_entry_class)
        self.base_entry = base_entry
        super(Relationship, self).__init__()


    def _fresh_queryset(self):
        """Return a QuerySet for this relationship using self.base_entry."""
        raise NotImplementedError


    @classmethod
    def from_uri_args(cls, *args, **kwargs):
        base_entry = cls.base_entry_class.from_uri_args(*args, **kwargs)
        return cls(base_entry)


    def _uri_args(self):
        return self.base_entry._uri_args()


    @classmethod
    def _read_hrefs(cls, links):
        return [link['href'] for link in links]


    @classmethod
    def _input_collection_hrefs(cls, input_data):
        """Get the members of a user-provided collection.

        Tries to be flexible about formats accepted from the user.
        @returns a list of hrefs
        """
        if isinstance(input_data, dict) and 'members' in input_data:
            # this mirrors the output representation for collections
            # guard against accidental truncation of the relationship due to
            # paging
            is_partial_collection = ('total_results' in input_data
                                     and 'items_per_page' in input_data
                                     and input_data['total_results'] >
                                         input_data['items_per_page'])
            if is_partial_collection:
                raise exceptions.BadRequest('You must retreive the full '
                                            'collection to perform updates')

            return cls._read_hrefs(input_data['members'])
        if isinstance(input_data, list):
            if not input_data:
                return input_data
            if isinstance(input_data[0], dict):
                # assume it's a list of links
                return cls._read_hrefs(input_data)
            if isinstance(input_data[0], basestring):
                # assume it's a list of hrefs
                return input_data
        raise exceptions.BadRequest('Cannot understand collection in input: %r'
                                    % input_data)


    def put(self, request):
        input_data = self._decoded_input(request)
        self.update(input_data)
        return self.get(request)


    def update(self, input_data):
        hrefs = self._input_collection_hrefs(input_data)
        instances = [self.entry_class.resolve_uri(href).instance
                     for href in hrefs]
        self._update_relationship(instances)


    def _update_relationship(self, related_instances):
        raise NotImplementedError
