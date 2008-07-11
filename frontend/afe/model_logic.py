"""
Extensions to Django's model logic.
"""

from django.db import models as dbmodels, backend, connection
from django.utils import datastructures
from frontend.afe import readonly_connection

class ValidationError(Exception):
    """\
    Data validation error in adding or updating an object.  The associated
    value is a dictionary mapping field names to error strings.
    """


def _wrap_with_readonly(method):
        def wrapper_method(*args, **kwargs):
            readonly_connection.connection.set_django_connection()
            try:
                return method(*args, **kwargs)
            finally:
                readonly_connection.connection.unset_django_connection()
        wrapper_method.__name__ = method.__name__
        return wrapper_method


def _wrap_generator_with_readonly(generator):
    """
    We have to wrap generators specially.  Assume it performs
    the query on the first call to next().
    """
    def wrapper_generator(*args, **kwargs):
        generator_obj = generator(*args, **kwargs)
        readonly_connection.connection.set_django_connection()
        try:
            first_value = generator_obj.next()
        finally:
            readonly_connection.connection.unset_django_connection()
        yield first_value

        while True:
            yield generator_obj.next()

    wrapper_generator.__name__ = generator.__name__
    return wrapper_generator


def _make_queryset_readonly(queryset):
    """
    Wrap all methods that do database queries with a readonly connection.
    """
    db_query_methods = ['count', 'get', 'get_or_create', 'latest', 'in_bulk',
                        'delete']
    for method_name in db_query_methods:
        method = getattr(queryset, method_name)
        wrapped_method = _wrap_with_readonly(method)
        setattr(queryset, method_name, wrapped_method)

    queryset.iterator = _wrap_generator_with_readonly(queryset.iterator)


class ReadonlyQuerySet(dbmodels.query.QuerySet):
    """
    QuerySet object that performs all database queries with the read-only
    connection.
    """
    def __init__(self, model=None):
        super(ReadonlyQuerySet, self).__init__(model)
        _make_queryset_readonly(self)


    def values(self, *fields):
        return self._clone(klass=ReadonlyValuesQuerySet, _fields=fields)


class ReadonlyValuesQuerySet(dbmodels.query.ValuesQuerySet):
    def __init__(self, model=None):
        super(ReadonlyValuesQuerySet, self).__init__(model)
        _make_queryset_readonly(self)


class ExtendedManager(dbmodels.Manager):
    """\
    Extended manager supporting subquery filtering.
    """

    class _CustomJoinQ(dbmodels.Q):
        """
        Django "Q" object supporting a custom suffix for join aliases.See
        filter_custom_join() for why this can be useful.
        """

        def __init__(self, join_suffix, **kwargs):
            super(ExtendedManager._CustomJoinQ, self).__init__(**kwargs)
            self._join_suffix = join_suffix


        @staticmethod
        def _substitute_aliases(renamed_aliases, condition):
            for old_alias, new_alias in renamed_aliases:
                    condition = condition.replace(backend.quote_name(old_alias),
                                                  backend.quote_name(new_alias))
            return condition


        @staticmethod
        def _unquote_name(name):
            'This may be MySQL specific'
            if backend.quote_name(name) == name:
                return name[1:-1]
            return name


        def get_sql(self, opts):
            joins, where, params = (
                super(ExtendedManager._CustomJoinQ, self).get_sql(opts))

            new_joins = datastructures.SortedDict()

            # rename all join aliases and correct references in later joins
            renamed_tables = []
            # using iteritems seems to mess up the ordering here
            for alias, (table, join_type, condition) in joins.items():
                alias = self._unquote_name(alias)
                new_alias = alias + self._join_suffix
                renamed_tables.append((alias, new_alias))
                condition = self._substitute_aliases(renamed_tables, condition)
                new_alias = backend.quote_name(new_alias)
                new_joins[new_alias] = (table, join_type, condition)

            # correct references in where
            new_where = []
            for clause in where:
                new_where.append(
                    self._substitute_aliases(renamed_tables, clause))

            return new_joins, new_where, params


    def filter_custom_join(self, join_suffix, **kwargs):
        """
        Just like Django filter(), but allows the user to specify a custom
        suffix for the join aliases involves in the filter.  This makes it
        possible to join against a table multiple times (as long as a different
        suffix is used each time), which is necessary for certain queries.
        """
        filter_object = self._CustomJoinQ(join_suffix, **kwargs)
        return self.complex_filter(filter_object)


    @staticmethod
    def _get_quoted_field(table, field):
        return (backend.quote_name(table) + '.' + backend.quote_name(field))


    def _get_key_on_this_table(self, key_field=None):
        if key_field is None:
            # default to primary key
            key_field = self.model._meta.pk.column
        return self._get_quoted_field(self.model._meta.db_table, key_field)



class ValidObjectsManager(ExtendedManager):
    """
    Manager returning only objects with invalid=False.
    """
    def get_query_set(self):
        queryset = super(ValidObjectsManager, self).get_query_set()
        return queryset.filter(invalid=False)


class ModelExtensions(object):
    """\
    Mixin with convenience functions for models, built on top of the
    default Django model functions.
    """
    # TODO: at least some of these functions really belong in a custom
    # Manager class

    field_dict = None
    # subclasses should override if they want to support smart_get() by name
    name_field = None


    @classmethod
    def get_field_dict(cls):
        if cls.field_dict is None:
            cls.field_dict = {}
            for field in cls._meta.fields:
                cls.field_dict[field.name] = field
        return cls.field_dict


    @classmethod
    def clean_foreign_keys(cls, data):
        """\
        -Convert foreign key fields in data from <field>_id to just
        <field>.
        -replace foreign key objects with their IDs
        This method modifies data in-place.
        """
        for field in cls._meta.fields:
            if not field.rel:
                continue
            if (field.attname != field.name and
                field.attname in data):
                data[field.name] = data[field.attname]
                del data[field.attname]
            value = data[field.name]
            if isinstance(value, dbmodels.Model):
                data[field.name] = value.id


    # TODO(showard) - is there a way to not have to do this?
    @classmethod
    def provide_default_values(cls, data):
        """\
        Provide default values for fields with default values which have
        nothing passed in.

        For CharField and TextField fields with "blank=True", if nothing
        is passed, we fill in an empty string value, even if there's no
        default set.
        """
        new_data = dict(data)
        field_dict = cls.get_field_dict()
        for name, obj in field_dict.iteritems():
            if data.get(name) is not None:
                continue
            if obj.default is not dbmodels.fields.NOT_PROVIDED:
                new_data[name] = obj.default
            elif (isinstance(obj, dbmodels.CharField) or
                  isinstance(obj, dbmodels.TextField)):
                new_data[name] = ''
        return new_data


    @classmethod
    def convert_human_readable_values(cls, data, to_human_readable=False):
        """\
        Performs conversions on user-supplied field data, to make it
        easier for users to pass human-readable data.

        For all fields that have choice sets, convert their values
        from human-readable strings to enum values, if necessary.  This
        allows users to pass strings instead of the corresponding
        integer values.

        For all foreign key fields, call smart_get with the supplied
        data.  This allows the user to pass either an ID value or
        the name of the object as a string.

        If to_human_readable=True, perform the inverse - i.e. convert
        numeric values to human readable values.

        This method modifies data in-place.
        """
        field_dict = cls.get_field_dict()
        for field_name in data:
            if data[field_name] is None:
                continue
            field_obj = field_dict[field_name]
            # convert enum values
            if field_obj.choices:
                for choice_data in field_obj.choices:
                    # choice_data is (value, name)
                    if to_human_readable:
                        from_val, to_val = choice_data
                    else:
                        to_val, from_val = choice_data
                    if from_val == data[field_name]:
                        data[field_name] = to_val
                        break
            # convert foreign key values
            elif field_obj.rel:
                dest_obj = field_obj.rel.to.smart_get(
                    data[field_name])
                if (to_human_readable and
                    dest_obj.name_field is not None):
                    data[field_name] = (
                        getattr(dest_obj,
                                dest_obj.name_field))
                else:
                    data[field_name] = dest_obj.id


    @classmethod
    def validate_field_names(cls, data):
        'Checks for extraneous fields in data.'
        errors = {}
        field_dict = cls.get_field_dict()
        for field_name in data:
            if field_name not in field_dict:
                errors[field_name] = 'No field of this name'
        return errors


    @classmethod
    def prepare_data_args(cls, data, kwargs):
        'Common preparation for add_object and update_object'
        data = dict(data) # don't modify the default keyword arg
        data.update(kwargs)
        # must check for extraneous field names here, while we have the
        # data in a dict
        errors = cls.validate_field_names(data)
        if errors:
            raise ValidationError(errors)
        cls.convert_human_readable_values(data)
        return data


    def validate_unique(self):
        """\
        Validate that unique fields are unique.  Django manipulators do
        this too, but they're a huge pain to use manually.  Trust me.
        """
        errors = {}
        cls = type(self)
        field_dict = self.get_field_dict()
        manager = cls.get_valid_manager()
        for field_name, field_obj in field_dict.iteritems():
            if not field_obj.unique:
                continue

            value = getattr(self, field_name)
            existing_objs = manager.filter(**{field_name : value})
            num_existing = existing_objs.count()

            if num_existing == 0:
                continue
            if num_existing == 1 and existing_objs[0].id == self.id:
                continue
            errors[field_name] = (
                'This value must be unique (%s)' % (value))
        return errors


    def do_validate(self):
        errors = self.validate()
        unique_errors = self.validate_unique()
        for field_name, error in unique_errors.iteritems():
            errors.setdefault(field_name, error)
        if errors:
            raise ValidationError(errors)


    # actually (externally) useful methods follow

    @classmethod
    def add_object(cls, data={}, **kwargs):
        """\
        Returns a new object created with the given data (a dictionary
        mapping field names to values). Merges any extra keyword args
        into data.
        """
        data = cls.prepare_data_args(data, kwargs)
        data = cls.provide_default_values(data)
        obj = cls(**data)
        obj.do_validate()
        obj.save()
        return obj


    def update_object(self, data={}, **kwargs):
        """\
        Updates the object with the given data (a dictionary mapping
        field names to values).  Merges any extra keyword args into
        data.
        """
        data = self.prepare_data_args(data, kwargs)
        for field_name, value in data.iteritems():
            if value is not None:
                setattr(self, field_name, value)
        self.do_validate()
        self.save()


    @classmethod
    def query_objects(cls, filter_data, valid_only=True):
        """\
        Returns a QuerySet object for querying the given model_class
        with the given filter_data.  Optional special arguments in
        filter_data include:
        -query_start: index of first return to return
        -query_limit: maximum number of results to return
        -sort_by: list of fields to sort on.  prefixing a '-' onto a
         field name changes the sort to descending order.
        -extra_args: keyword args to pass to query.extra() (see Django
         DB layer documentation)
         -extra_where: extra WHERE clause to append
        """
        query_start = filter_data.pop('query_start', None)
        query_limit = filter_data.pop('query_limit', None)
        if query_start and not query_limit:
            raise ValueError('Cannot pass query_start without '
                             'query_limit')
        sort_by = filter_data.pop('sort_by', [])
        extra_args = filter_data.pop('extra_args', {})
        extra_where = filter_data.pop('extra_where', None)
        if extra_where:
            # escape %'s
            extra_where = extra_where.replace('%', '%%')
            extra_args.setdefault('where', []).append(extra_where)

        # filters
        query_dict = {}
        for field, value in filter_data.iteritems():
            query_dict[field] = value
        if valid_only:
            manager = cls.get_valid_manager()
        else:
            manager = cls.objects
        query = manager.filter(**query_dict).distinct()

        # other arguments
        if extra_args:
            query = query.extra(**extra_args)
            query = query._clone(klass=ReadonlyQuerySet)

        # sorting + paging
        assert isinstance(sort_by, list) or isinstance(sort_by, tuple)
        query = query.order_by(*sort_by)
        if query_start is not None and query_limit is not None:
            query_limit += query_start
        return query[query_start:query_limit]


    @classmethod
    def query_count(cls, filter_data):
        """\
        Like query_objects, but retreive only the count of results.
        """
        filter_data.pop('query_start', None)
        filter_data.pop('query_limit', None)
        return cls.query_objects(filter_data).count()


    @classmethod
    def clean_object_dicts(cls, field_dicts):
        """\
        Take a list of dicts corresponding to object (as returned by
        query.values()) and clean the data to be more suitable for
        returning to the user.
        """
        for i in range(len(field_dicts)):
            cls.clean_foreign_keys(field_dicts[i])
            cls.convert_human_readable_values(
                field_dicts[i], to_human_readable=True)


    @classmethod
    def list_objects(cls, filter_data):
        """\
        Like query_objects, but return a list of dictionaries.
        """
        query = cls.query_objects(filter_data)
        field_dicts = list(query.values())
        cls.clean_object_dicts(field_dicts)
        return field_dicts


    @classmethod
    def smart_get(cls, *args, **kwargs):
        """\
        smart_get(integer) -> get object by ID
        smart_get(string) -> get object by name_field
        smart_get(keyword args) -> normal ModelClass.objects.get()
        """
        assert bool(args) ^ bool(kwargs)
        if args:
            assert len(args) == 1
            arg = args[0]
            if isinstance(arg, int) or isinstance(arg, long):
                return cls.objects.get(id=arg)
            if isinstance(arg, str) or isinstance(arg, unicode):
                return cls.objects.get(
                    **{cls.name_field : arg})
            raise ValueError(
                'Invalid positional argument: %s (%s)' % (
                str(arg), type(arg)))
        return cls.objects.get(**kwargs)


    def get_object_dict(self):
        """\
        Return a dictionary mapping fields to this object's values.
        """
        object_dict = dict((field_name, getattr(self, field_name))
                           for field_name
                           in self.get_field_dict().iterkeys())
        self.clean_object_dicts([object_dict])
        return object_dict


    @classmethod
    def get_valid_manager(cls):
        return cls.objects


class ModelWithInvalid(ModelExtensions):
    """
    Overrides model methods save() and delete() to support invalidation in
    place of actual deletion.  Subclasses must have a boolean "invalid"
    field.
    """

    def save(self):
        # see if this object was previously added and invalidated
        my_name = getattr(self, self.name_field)
        filters = {self.name_field : my_name, 'invalid' : True}
        try:
            old_object = self.__class__.objects.get(**filters)
        except self.DoesNotExist:
            # no existing object
            super(ModelWithInvalid, self).save()
            return

        self.id = old_object.id
        super(ModelWithInvalid, self).save()


    def clean_object(self):
        """
        This method is called when an object is marked invalid.
        Subclasses should override this to clean up relationships that
        should no longer exist if the object were deleted."""
        pass


    def delete(self):
        assert not self.invalid
        self.invalid = True
        self.save()
        self.clean_object()


    @classmethod
    def get_valid_manager(cls):
        return cls.valid_objects


    class Manipulator(object):
        """
        Force default manipulators to look only at valid objects -
        otherwise they will match against invalid objects when checking
        uniqueness.
        """
        @classmethod
        def _prepare(cls, model):
            super(ModelWithInvalid.Manipulator, cls)._prepare(model)
            cls.manager = model.valid_objects
