import cgi
import re
import time
import urllib

import django.core.exceptions
import simplejson
from autotest.frontend.afe import model_logic
from autotest.frontend.shared import exceptions, query_lib
from django import http
from django.core import urlresolvers
from django.utils import datastructures

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
    _permitted_methods = None  # subclasses must override this

    def __init__(self, request):
        assert self._permitted_methods
        # this request should be used for global environment info, like
        # constructing absolute URIs.  it should not be used for query
        # parameters, because the request may not have been for this particular
        # resource.
        self._request = request
        # this dict will contain the applicable query parameters
        self._query_params = datastructures.MultiValueDict()

    @classmethod
    def dispatch_request(cls, request, *args, **kwargs):
        # handle a request directly
        try:
            try:
                instance = cls.from_uri_args(request, **kwargs)
            except django.core.exceptions.ObjectDoesNotExist, exc:
                raise http.Http404(exc)

            instance.read_query_parameters(request.GET)
            return instance.handle_request()
        except exceptions.RequestError, exc:
            return exc.response

    def handle_request(self):
        if self._request.method.upper() not in self._permitted_methods:
            return http.HttpResponseNotAllowed(self._permitted_methods)

        handler = getattr(self, self._request.method.lower())
        return handler()

    # the handler methods below only need to be overridden if the resource
    # supports the method
    def get(self):
        """Handle a GET request.

        :return: an HttpResponse
        """
        raise NotImplementedError

    def post(self):
        """Handle a POST request.

        :return: an HttpResponse
        """
        raise NotImplementedError

    def put(self):
        """Handle a PUT request.

        :return: an HttpResponse
        """
        raise NotImplementedError

    def delete(self):
        """Handle a DELETE request.

        :return: an HttpResponse
        """
        raise NotImplementedError

    @classmethod
    def from_uri_args(cls, request, **kwargs):
        """Construct an instance from URI args.

        Default implementation for resources with no URI args.
        """
        return cls(request)

    def _uri_args(self):
        """Return kwargs for a URI reference to this resource.

        Default implementation for resources with no URI args.
        """
        return {}

    def _query_parameters_accepted(self):
        """Return sequence of tuples (name, description) for query parameters.

        Documents the available query parameters for GETting this resource.
        Default implementation for resources with no parameters.
        """
        return ()

    def read_query_parameters(self, parameters):
        """Read relevant query parameters from a Django MultiValueDict."""
        params_acccepted = set(param_name for param_name, _
                               in self._query_parameters_accepted())
        for name, values in parameters.iterlists():
            base_name = name.split(':', 1)[0]
            if base_name in params_acccepted:
                self._query_params.setlist(name, values)

    def set_query_parameters(self, **parameters):
        """Set query parameters programmatically."""
        self._query_params.update(parameters)

    def href(self, query_params=None):
        """Return URI to this resource."""
        kwargs = self._uri_args()
        path = urlresolvers.reverse(self.dispatch_request, kwargs=kwargs)
        full_query_params = datastructures.MultiValueDict(self._query_params)
        if query_params:
            full_query_params.update(query_params)
        if full_query_params:
            path += '?' + urllib.urlencode(full_query_params.lists(),
                                           doseq=True)
        return self._request.build_absolute_uri(path)

    def resolve_uri(self, uri):
        # check for absolute URIs
        match = re.match(r'(?P<root>https?://[^/]+)(?P<path>/.*)', uri)
        if match:
            # is this URI for a different host?
            my_root = self._request.build_absolute_uri('/')
            request_root = match.group('root') + '/'
            if my_root != request_root:
                # might support this in the future, but not now
                raise exceptions.BadRequest('Unable to resolve remote URI %s'
                                            % uri)
            uri = match.group('path')

        try:
            view_method, args, kwargs = urlresolvers.resolve(uri)
        except http.Http404:
            raise exceptions.BadRequest('Unable to resolve URI %s' % uri)
        resource_class = view_method.im_self  # class owning this classmethod
        return resource_class.from_uri_args(self._request, **kwargs)

    def resolve_link(self, link):
        if isinstance(link, dict):
            uri = link['href']
        elif isinstance(link, basestring):
            uri = link
        else:
            raise exceptions.BadRequest('Unable to understand link %s' % link)
        return self.resolve_uri(uri)

    def link(self, query_params=None):
        return {'href': self.href(query_params=query_params)}

    def _query_parameters_response(self):
        return dict((name, description)
                    for name, description in self._query_parameters_accepted())

    def _basic_response(self, content):
        """Construct and return a simple 200 response."""
        assert isinstance(content, dict)
        query_parameters = self._query_parameters_response()
        if query_parameters:
            content['query_parameters'] = query_parameters
        encoded_content = simplejson.dumps(content)
        return http.HttpResponse(encoded_content,
                                 content_type=_JSON_CONTENT_TYPE)

    def _decoded_input(self):
        content_type = self._request.META.get('CONTENT_TYPE',
                                              _JSON_CONTENT_TYPE)
        raw_data = self._request.raw_post_data
        if content_type == _JSON_CONTENT_TYPE:
            try:
                raw_dict = simplejson.loads(raw_data)
            except ValueError, exc:
                raise exceptions.BadRequest('Error decoding request body: '
                                            '%s\n%r' % (exc, raw_data))
            if not isinstance(raw_dict, dict):
                raise exceptions.BadRequest('Expected dict input, got %s: %r' %
                                            (type(raw_dict), raw_dict))
        elif content_type == 'application/x-www-form-urlencoded':
            cgi_dict = cgi.parse_qs(raw_data)  # django won't do this for PUT
            raw_dict = {}
            for key, values in cgi_dict.items():
                value = values[-1]  # take last value if multiple were given
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
            timezone_join = ''  # minus sign comes from number itself
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

    @classmethod
    def add_query_selectors(cls, query_processor):
        """Sbuclasses may override this to support querying."""
        pass

    def short_representation(self):
        return self.link()

    def full_representation(self):
        return self.short_representation()

    def get(self):
        return self._basic_response(self.full_representation())

    def put(self):
        try:
            self.update(self._decoded_input())
        except model_logic.ValidationError, exc:
            raise exceptions.BadRequest('Invalid input: %s' % exc)
        return self._basic_response(self.full_representation())

    def _delete_entry(self):
        raise NotImplementedError

    def delete(self):
        self._delete_entry()
        return http.HttpResponse(status=204)  # No content

    def create_instance(self, input_dict, containing_collection):
        raise NotImplementedError

    def update(self, input_dict):
        raise NotImplementedError


class InstanceEntry(Entry):

    class NullEntry(object):

        def link(self):
            return None

        def short_representation(self):
            return None

    _null_entry = NullEntry()
    _permitted_methods = ('GET', 'PUT', 'DELETE')
    model = None  # subclasses must override this with a Django model class

    def __init__(self, request, instance):
        assert self.model is not None
        super(InstanceEntry, self).__init__(request)
        self.instance = instance
        self._is_prepared_for_full_representation = False

    @classmethod
    def from_optional_instance(cls, request, instance):
        if instance is None:
            return cls._null_entry
        return cls(request, instance)

    def _delete_entry(self):
        self.instance.delete()

    def full_representation(self):
        self.prepare_for_full_representation([self])
        return super(InstanceEntry, self).full_representation()

    @classmethod
    def prepare_for_full_representation(cls, entries):
        """
        Prepare the given list of entries to generate full representations.

        This method delegates to _do_prepare_for_full_representation(), which
        subclasses may override as necessary to do the actual processing.  This
        method also marks the instance as prepared, so it's safe to call this
        multiple times with the same instance(s) without wasting work.
        """
        not_prepared = [entry for entry in entries
                        if not entry._is_prepared_for_full_representation]
        cls._do_prepare_for_full_representation([entry.instance
                                                 for entry in not_prepared])
        for entry in not_prepared:
            entry._is_prepared_for_full_representation = True

    @classmethod
    def _do_prepare_for_full_representation(cls, instances):
        """
        Subclasses may override this to gather data as needed for full
        representations of the given model instances.  Typically, this involves
        querying over related objects, and this method offers a chance to query
        for many instances at once, which can provide a great performance
        benefit.
        """
        pass


class Collection(Resource):
    _DEFAULT_ITEMS_PER_PAGE = 50

    _permitted_methods = ('GET', 'POST')

    # subclasses must override these
    queryset = None  # or override _fresh_queryset() directly
    entry_class = None

    def __init__(self, request):
        super(Collection, self).__init__(request)
        assert self.entry_class is not None
        if isinstance(self.entry_class, basestring):
            type(self).entry_class = _resolve_class_path(self.entry_class)

        self._query_processor = query_lib.QueryProcessor()
        self.entry_class.add_query_selectors(self._query_processor)

    def _query_parameters_accepted(self):
        params = [('start_index', 'Index of first member to include'),
                  ('items_per_page', 'Number of members to include'),
                  ('full_representations',
                   'True to include full representations of members')]
        for selector in self._query_processor.selectors():
            params.append((selector.name, selector.doc))
        return params

    def _fresh_queryset(self):
        assert self.queryset is not None
        # always copy the queryset before using it to avoid caching
        return self.queryset.all()

    def _entry_from_instance(self, instance):
        # entry_class is actually turned into a callable, so this is OK
        # pylint: disable=E1102
        return self.entry_class(self._request, instance)

    def _representation(self, entry_instances):
        entries = [self._entry_from_instance(instance)
                   for instance in entry_instances]

        want_full_representation = self._read_bool_parameter(
            'full_representations')
        if want_full_representation:
            self.entry_class.prepare_for_full_representation(entries)

        members = []
        for entry in entries:
            if want_full_representation:
                rep = entry.full_representation()
            else:
                rep = entry.short_representation()
            members.append(rep)

        rep = self.link()
        rep.update({'members': members})
        return rep

    def _read_bool_parameter(self, name):
        if name not in self._query_params:
            return False
        return (self._query_params[name].lower() == 'true')

    def _read_int_parameter(self, name, default):
        if name not in self._query_params:
            return default
        input_value = self._query_params[name]
        try:
            return int(input_value)
        except ValueError:
            raise exceptions.BadRequest('Invalid non-numeric value for %s: %r'
                                        % (name, input_value))

    def _apply_form_query(self, queryset):
        """Apply any query selectors passed as form variables."""
        for parameter, values in self._query_params.lists():
            if ':' in parameter:
                parameter, comparison_type = parameter.split(':', 1)
            else:
                comparison_type = None

            if not self._query_processor.has_selector(parameter):
                continue
            for value in values:  # forms keys can have multiple values
                queryset = self._query_processor.apply_selector(
                    queryset, parameter, value,
                    comparison_type=comparison_type)
        return queryset

    def _filtered_queryset(self):
        return self._apply_form_query(self._fresh_queryset())

    def get(self):
        queryset = self._filtered_queryset()

        items_per_page = self._read_int_parameter('items_per_page',
                                                  self._DEFAULT_ITEMS_PER_PAGE)
        start_index = self._read_int_parameter('start_index', 0)
        page = queryset[start_index:(start_index + items_per_page)]

        rep = self._representation(page)
        rep.update({'total_results': len(queryset),
                    'start_index': start_index,
                    'items_per_page': items_per_page})
        return self._basic_response(rep)

    def full_representation(self):
        # careful, this rep can be huge for large collections
        return self._representation(self._fresh_queryset())

    def post(self):
        input_dict = self._decoded_input()
        try:
            instance = self.entry_class.create_instance(input_dict, self)
            entry = self._entry_from_instance(instance)
            entry.update(input_dict)
        except model_logic.ValidationError, exc:
            raise exceptions.BadRequest('Invalid input: %s' % exc)
        # RFC 2616 specifies that we provide the new URI in both the Location
        # header and the body
        response = http.HttpResponse(status=201,  # Created
                                     content=entry.href())
        response['Location'] = entry.href()
        return response


class Relationship(Entry):
    _permitted_methods = ('GET', 'DELETE')

    # subclasses must override this with a dict mapping name to entry class
    related_classes = {}

    def __init__(self, **kwargs):
        assert len(self.related_classes) == 2
        self.entries = dict((name, kwargs[name])
                            for name in self.related_classes)
        for name in self.related_classes:  # sanity check
            assert isinstance(self.entries[name], self.related_classes[name])

        # just grab the request from one of the entries
        some_entry = self.entries.itervalues().next()
        super(Relationship, self).__init__(some_entry._request)

    @classmethod
    def from_uri_args(cls, request, **kwargs):
        # kwargs contains URI args for each entry
        entries = {}
        for name, entry_class in cls.related_classes.iteritems():
            entries[name] = entry_class.from_uri_args(request, **kwargs)
        return cls(**entries)

    def _uri_args(self):
        kwargs = {}
        for name, entry in self.entries.iteritems():
            kwargs.update(entry._uri_args())
        return kwargs

    def short_representation(self):
        rep = self.link()
        for name, entry in self.entries.iteritems():
            rep[name] = entry.short_representation()
        return rep

    @classmethod
    def _get_related_manager(cls, instance):
        """Get the related objects manager for the given instance.

        The instance must be one of the related classes.  This method will
        return the related manager from that instance to instances of the other
        related class.
        """
        this_model = type(instance)
        models = [entry_class.model for entry_class
                  in cls.related_classes.values()]
        if isinstance(instance, models[0]):
            this_model, other_model = models
        else:
            other_model, this_model = models

        _, field = this_model.objects.determine_relationship(other_model)
        this_models_fields = (this_model._meta.fields +
                              this_model._meta.many_to_many)
        if field in this_models_fields:
            manager_name = field.attname
        else:
            # related manager is on other_model, get name of reverse related
            # manager on this_model
            manager_name = field.related.get_accessor_name()

        return getattr(instance, manager_name)

    def _delete_entry(self):
        # choose order arbitrarily
        entry, other_entry = self.entries.itervalues()
        related_manager = self._get_related_manager(entry.instance)
        related_manager.remove(other_entry.instance)

    @classmethod
    def create_instance(cls, input_dict, containing_collection):
        other_name = containing_collection.unfixed_name
        cls._check_for_required_fields(input_dict, (other_name,))
        entry = containing_collection.fixed_entry
        other_entry = containing_collection.resolve_link(input_dict[other_name])
        related_manager = cls._get_related_manager(entry.instance)
        related_manager.add(other_entry.instance)
        return other_entry.instance

    def update(self, input_dict):
        pass


class RelationshipCollection(Collection):

    def __init__(self, request=None, fixed_entry=None):
        if request is None:
            request = fixed_entry._request
        super(RelationshipCollection, self).__init__(request)

        assert issubclass(self.entry_class, Relationship)
        self.related_classes = self.entry_class.related_classes
        self.fixed_name = None
        self.fixed_entry = None
        self.unfixed_name = None
        self.related_manager = None

        if fixed_entry is not None:
            self._set_fixed_entry(fixed_entry)
            entry_uri_arg = self.fixed_entry._uri_args().values()[0]
            self._query_params[self.fixed_name] = entry_uri_arg

    def _set_fixed_entry(self, entry):
        """Set the fixed entry for this collection.

        The entry must be an instance of one of the related entry classes.  This
        method must be called before a relationship is used.  It gets called
        either from the constructor (when collections are instantiated from
        other resource handling code) or from read_query_parameters() (when a
        request is made directly for the collection.
        """
        names = self.related_classes.keys()
        if isinstance(entry, self.related_classes[names[0]]):
            self.fixed_name, self.unfixed_name = names
        else:
            assert isinstance(entry, self.related_classes[names[1]])
            self.unfixed_name, self.fixed_name = names
        self.fixed_entry = entry
        self.unfixed_class = self.related_classes[self.unfixed_name]
        self.related_manager = self.entry_class._get_related_manager(
            entry.instance)

    def _query_parameters_accepted(self):
        return [(name, 'Show relationships for this %s' % entry_class.__name__)
                for name, entry_class
                in self.related_classes.iteritems()]

    def _resolve_query_param(self, name, uri_arg):
        entry_class = self.related_classes[name]
        return entry_class.from_uri_args(self._request, uri_arg)

    def read_query_parameters(self, query_params):
        super(RelationshipCollection, self).read_query_parameters(query_params)
        if not self._query_params:
            raise exceptions.BadRequest(
                'You must specify one of the parameters %s and %s'
                % tuple(self.related_classes.keys()))
        query_items = self._query_params.items()
        fixed_entry = self._resolve_query_param(*query_items[0])
        self._set_fixed_entry(fixed_entry)

        if len(query_items) > 1:
            other_fixed_entry = self._resolve_query_param(*query_items[1])
            self.related_manager = self.related_manager.filter(
                pk=other_fixed_entry.instance.id)

    def _entry_from_instance(self, instance):
        unfixed_entry = self.unfixed_class(self._request, instance)
        entries = {self.fixed_name: self.fixed_entry,
                   self.unfixed_name: unfixed_entry}
        # entry_class is actually turned into a callable, so this is OK
        # pylint: disable=E1102
        return self.entry_class(**entries)

    def _fresh_queryset(self):
        return self.related_manager.all()
