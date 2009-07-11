#
# Copyright 2008 Google Inc. Released under the GPL v2

import compiler, textwrap, types


REQUIRED_VARS = set(['author', 'doc', 'name', 'time', 'test_class',
                     'test_category', 'test_type'])

class ControlVariableException(Exception):
    pass


class ControlData(object):
    def __init__(self, vars, path, raise_warnings=False):
        # Defaults
        self.path = path
        self.dependencies = set()
        self.experimental = False
        self.run_verify = True
        self.sync_count = 1

        diff = REQUIRED_VARS - set(vars)
        if len(diff) > 0:
            warning = ("WARNING: Not all required control "
                       "variables were specified in %s.  Please define "
                       "%s.") % (self.path, ', '.join(diff))
            if raise_warnings:
                raise ControlVariableException(warning)
            print textwrap.wrap(warning, 80)

        for key, val in vars.iteritems():
            try:
                self.set_attr(key, val, raise_warnings)
            except Exception, e:
                if raise_warnings:
                    raise
                print "WARNING: %s; skipping" % e


    def set_attr(self, attr, val, raise_warnings=False):
        attr = attr.lower()
        try:
            set_fn = getattr(self, 'set_%s' % attr)
            set_fn(val)
        except AttributeError:
            # This must not be a variable we care about
            pass


    def _set_string(self, attr, val):
        val = str(val)
        setattr(self, attr, val)


    def _set_option(self, attr, val, options):
        val = str(val)
        if val.lower() not in [x.lower() for x in options]:
            raise ValueError("%s must be one of the following "
                             "options: %s" % (attr,
                             ', '.join(options)))
        setattr(self, attr, val)


    def _set_bool(self, attr, val):
        val = str(val).lower()
        if val == "false":
            val = False
        elif val == "true":
            val = True
        else:
            msg = "%s must be either true or false" % attr
            raise ValueError(msg)
        setattr(self, attr, val)


    def _set_int(self, attr, val, min=None, max=None):
        val = int(val)
        if min is not None and min > val:
            raise ValueError("%s is %d, which is below the "
                             "minimum of %d" % (attr, val, min))
        if max is not None and max < val:
            raise ValueError("%s is %d, which is above the "
                             "maximum of %d" % (attr, val, max))
        setattr(self, attr, val)


    def _set_set(self, attr, val):
        val = str(val)
        items = [x.strip() for x in val.split(',')]
        setattr(self, attr, set(items))


    def set_author(self, val):
        self._set_string('author', val)


    def set_dependencies(self, val):
        self._set_set('dependencies', val)


    def set_doc(self, val):
        self._set_string('doc', val)


    def set_experimental(self, val):
        self._set_bool('experimental', val)


    def set_name(self, val):
        self._set_string('name', val)


    def set_run_verify(self, val):
        self._set_bool('run_verify', val)


    def set_sync_count(self, val):
        self._set_int('sync_count', val, min=1)


    def set_time(self, val):
        self._set_option('time', val, ['short', 'medium', 'long'])


    def set_test_class(self, val):
        self._set_string('test_class', val.lower())


    def set_test_category(self, val):
        self._set_string('test_category', val.lower())


    def set_test_type(self, val):
        self._set_option('test_type', val, ['client', 'server'])


def _extract_const(n):
    assert(n.__class__ == compiler.ast.Assign)
    assert(n.expr.__class__ == compiler.ast.Const)
    assert(n.expr.value.__class__ in (str, int, float, unicode))
    assert(n.nodes.__class__ == list)
    assert(len(n.nodes) == 1)
    assert(n.nodes[0].__class__ == compiler.ast.AssName)
    assert(n.nodes[0].flags.__class__ == str)
    assert(n.nodes[0].name.__class__ == str)

    key = n.nodes[0].name.lower()
    val = str(n.expr.value).strip()

    return (key, val)


def _extract_name(n):
    assert(n.__class__ == compiler.ast.Assign)
    assert(n.expr.__class__ == compiler.ast.Name)
    assert(n.nodes.__class__ == list)
    assert(len(n.nodes) == 1)
    assert(n.nodes[0].__class__ == compiler.ast.AssName)
    assert(n.nodes[0].flags.__class__ == str)
    assert(n.nodes[0].name.__class__ == str)
    assert(n.expr.name in ('False', 'True', 'None'))

    key = n.nodes[0].name.lower()
    val = str(n.expr.name)

    return (key, val)


def parse_control(path, raise_warnings=False):
    try:
        mod = compiler.parseFile(path)
    except SyntaxError, e:
        raise ControlVariableException("Error parsing %s because %s" %
                                       (path, e))

    assert(mod.__class__ == compiler.ast.Module)
    assert(mod.node.__class__ == compiler.ast.Stmt)
    assert(mod.node.nodes.__class__ == list)

    vars = {}
    for n in mod.node.nodes:
        for fn in (_extract_const, _extract_name):
            try:
                key, val = fn(n)

                vars[key] = val
            except AssertionError, e:
                pass

    return ControlData(vars, path, raise_warnings)
