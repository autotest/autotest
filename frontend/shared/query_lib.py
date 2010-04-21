from autotest_lib.frontend.shared import exceptions

class ConstraintError(Exception):
    """Raised when an error occurs applying a Constraint."""


class QueryProcessor(object):
    def __init__(self):
        # maps selector name to (selector, constraint)
        self._selectors = {}
        self._alias_counter = 0


    def add_field_selector(self, name, field=None, value_transform=None,
                           doc=None):
        if not field:
            field = name
        self.add_selector(Selector(name, doc),
                          _FieldConstraint(field, value_transform))


    def add_related_existence_selector(self, name, model, field, doc=None):
        self.add_selector(
                Selector(name, doc),
                _RelatedExistenceConstraint(model, field,
                                            make_alias_fn=self.make_alias))


    def add_keyval_selector(self, name, model, key_field, value_field,
                            doc=None):
        self.add_selector(
                Selector(name, doc),
                _KeyvalConstraint(model, key_field, value_field,
                                  make_alias_fn=self.make_alias))


    def add_selector(self, selector, constraint):
        if self._selectors is None:
            self._selectors = {}
        self._selectors[selector.name] = (selector, constraint)


    def make_alias(self):
        self._alias_counter += 1
        return 'alias%s' % self._alias_counter


    def selectors(self):
        return tuple(selector for selector, constraint
                     in self._selectors.itervalues())


    def has_selector(self, selector_name):
        return selector_name in self._selectors


    def apply_selector(self, queryset, selector_name, value,
                       comparison_type=None, is_inverse=False):
        if comparison_type is None:
            comparison_type = 'equals'
        _, constraint = self._selectors[selector_name]
        try:
            return constraint.apply_constraint(queryset, value, comparison_type,
                                               is_inverse)
        except ConstraintError, exc:
            raise exceptions.BadRequest('Selector %s: %s'
                                        % (selector_name, exc))


    # common value conversions

    def read_boolean(self, boolean_input):
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
        if comparison_type == 'in':
            value = value.split(',')

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


class _KeyvalConstraint(Constraint):
    def __init__(self, model, key_field, value_field, make_alias_fn):
        self._model = model
        self._key_field = key_field
        self._value_field = value_field
        self._make_alias_fn = make_alias_fn


    def apply_constraint(self, queryset, value, comparison_type, is_inverse):
        if comparison_type not in (None, 'equals'):
            raise ConstraintError('Can only use equals or not equals with '
                                  'this selector')
        if '=' not in value:
            raise ConstraintError('You must specify a key=value pair for this '
                                  'selector')

        key, actual_value = value.split('=', 1)
        related_query = self._model.objects.filter(
                **{self._key_field: key, self._value_field: actual_value})
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
