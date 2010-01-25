from autotest_lib.frontend.shared import exceptions

class ConstraintError(Exception):
    """Raised when an error occurs applying a Constraint."""


class BaseQueryProcessor(object):
    # maps selector name to (selector, constraint)
    _selectors = None
    _alias_counter = 0


    @classmethod
    def _initialize_selectors(cls):
        if not cls._selectors:
            cls._selectors = {}
            cls._add_all_selectors()


    @classmethod
    def _add_all_selectors(cls):
        """
        Subclasses should override this to define which selectors they accept.
        """
        pass


    @classmethod
    def _add_field_selector(cls, name, field=None, value_transform=None,
                            doc=None):
        if not field:
            field = name
        cls._add_selector(Selector(name, doc),
                          _FieldConstraint(field, value_transform))


    @classmethod
    def _add_related_existence_selector(cls, name, model, field, doc=None):
        cls._add_selector(Selector(name, doc),
                          _RelatedExistenceConstraint(model, field,
                                                      cls.make_alias))


    @classmethod
    def _add_selector(cls, selector, constraint):
        cls._selectors[selector.name] = (selector, constraint)


    @classmethod
    def make_alias(cls):
        cls._alias_counter += 1
        return 'alias%s' % cls._alias_counter


    @classmethod
    def selectors(cls):
        cls._initialize_selectors()
        return tuple(selector for selector, constraint
                     in cls._selectors.itervalues())


    @classmethod
    def has_selector(cls, selector_name):
        cls._initialize_selectors()
        return selector_name in cls._selectors


    def apply_selector(self, queryset, selector_name, value,
                       comparison_type='equals', is_inverse=False):
        _, constraint = self._selectors[selector_name]
        try:
            return constraint.apply_constraint(queryset, value, comparison_type,
                                               is_inverse)
        except ConstraintError, exc:
            raise exceptions.BadRequest('Selector %s: %s'
                                        % (selector_name, exc))


    # common value conversions

    @classmethod
    def read_boolean(cls, boolean_input):
        if boolean_input.lower() == 'true':
            return True
        if boolean_input.lower() == 'false':
            return False
        raise exceptions.BadRequest('Invalid input for boolean: %r'
                                    % boolean_input)


class Selector(object):
    def __init__(self, name, doc):
        self.name = name
        self.doc = doc


class Constraint(object):
    def apply_constraint(self, queryset, value, comparison_type, is_inverse):
        raise NotImplementedError


class _FieldConstraint(Constraint):
    def __init__(self, field, value_transform=None):
        self._field = field
        self._value_transform = value_transform


    _COMPARISON_MAP = {
            'equals': 'exact',
            'lt': 'lt',
            'le': 'lte',
            'gt': 'gt',
            'ge': 'gte',
            'contains': 'contains',
            'startswith': 'startswith',
            'endswith': 'endswith',
            'in': 'in',
            }


    def apply_constraint(self, queryset, value, comparison_type, is_inverse):
        if self._value_transform:
            value = self._value_transform(value)

        kwarg_name = str(self._field + '__' +
                         self._COMPARISON_MAP[comparison_type])

        if is_inverse:
            return queryset.exclude(**{kwarg_name: value})
        else:
            return queryset.filter(**{kwarg_name: value})


class _RelatedExistenceConstraint(Constraint):
    def __init__(self, model, field, make_alias_fn):
        self._model = model
        self._field = field
        self._make_alias_fn = make_alias_fn


    def apply_constraint(self, queryset, value, comparison_type, is_inverse):
        if comparison_type not in (None, 'equals'):
            raise ConstraintError('Can only use equals or not equals with '
                                  'this selector')
        related_query = self._model.objects.filter(**{self._field: value})
        if not related_query:
            raise ConstraintError('%s %s not found' % (self._model_name, value))
        alias = self._make_alias_fn()
        queryset = queryset.model.objects.join_custom_field(queryset,
                                                            related_query,
                                                            alias)
        if is_inverse:
            condition = '%s.%s IS NULL'
        else:
            condition = '%s.%s IS NOT NULL'
        condition %= (alias,
                      queryset.model.objects.key_on_joined_table(related_query))

        queryset = queryset.model.objects.add_where(queryset, condition)

        return queryset
