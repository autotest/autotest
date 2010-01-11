"""Convenience methods for use to manipulate traffic control settings.

see http://linux.die.net/man/8/tc for details about traffic controls in linux.

Example
  import common
  from autotest_lib.client.bin.net.net_tc import *
  from autotest_lib.client.bin.net.net_utils import *

  class mock_netif(object):

    def __init__(self, name):
        self._name = name

    def get_name(self):
        return self._name


  netem_qdisc = netem()
  netem_qdisc.add_param('loss 100%')

  ack_filter = u32filter()
  ack_filter.add_rule('match ip protocol 6 0xff')
  ack_filter.add_rule('match u8 0x10 0x10 at nexthdr+13')
  ack_filter.set_dest_qdisc(netem_qdisc)

  root_qdisc = prio()
  root_qdisc.get_class(2).set_leaf_qdisc(netem_qdisc)
  root_qdisc.add_filter(ack_filter)

  lo_if = mock_netif('lo')

  root_qdisc.setup(lo_if)

  # run test here ...
  root_qdisc.restore(lo_if)

"""

import commands, os, re
import common
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin.net import net_utils

# TODO (chavey) clean up those global here and new_handle()
handle_counter = 0
INCR = 100


def new_handle():
    global handle_counter
    handle_counter += INCR
    return handle_counter


class tcclass(object):

    def __init__(self, handle, minor, leaf_qdisc=None):
        self._parent_class = None
        self._children = []
        self._leaf_qdisc = leaf_qdisc
        self._handle = handle
        self._minor = minor


    def get_leaf_qdisc(self):
        return self._leaf_qdisc


    def set_leaf_qdisc(self, leaf_qdisc):
        leaf_qdisc.set_parent_class(self)
        self._leaf_qdisc = leaf_qdisc


    def get_parent_class(self):
        return self._parent_class


    def set_parent_class(self, parent_class):
        self._parent_class = parent_class


    def get_minor(self):
        return self._minor


    def id(self):
        return '%s:%s' % (self._handle, self._minor)


    def add_child(self, child_class):
        child_class.set_parent_class(self)
        if child_class not in self._children:
            self._child.append(child_class)


    def setup(self, netif):
        # setup leaf qdisc
        if self._leaf_qdisc:
            self._leaf_qdisc.setup(netif)

        # setup child classes
        for child in self._children:
            child.setup()


    def restore(self, netif):
        # restore child classes
        children_copy = list(self._children)
        children_copy.reverse()
        for child in children_copy:
            child.restore()

        # restore leaf qdisc
        if self._leaf_qdisc:
            self._leaf_qdisc.restore(netif)


class tcfilter(object):

    _tc_cmd = 'tc filter %(cmd)s dev %(dev)s parent %(parent)s protocol ' \
               '%(protocol)s prio %(priority)s %(filtertype)s \\\n ' \
               '%(rules)s \\\n  flowid %(flowid)s'

    conf_device = 'dev'
    conf_parent = 'parent'
    conf_type = 'filtertype'
    conf_protocol = 'protocol'
    conf_priority = 'priority'
    conf_flowid = 'flowid'
    conf_command = 'cmd'
    conf_rules = 'cmd'
    conf_qdiscid = 'qdiscid'
    conf_name = 'name'
    conf_params = 'params'


    def __init__(self):
        self._parent_qdisc = None
        self._dest_qdisc = None
        self._protocol = 'ip'
        self._priority = 1
        self._handle = None
        self._tc_conf = None


    def get_parent_qdisc(self):
        return self._parent_qdisc


    def set_parent_qdisc(self, parent_qdisc):
        self._parent_qdisc = parent_qdisc


    def get_dest_qdisc(self):
        return self._dest_qdisc


    def set_dest_qdisc(self, dest_qdisc):
        self._dest_qdisc = dest_qdisc


    def get_protocol(self):
        return self._protocol


    def set_protocol(self, protocol):
        self._protocol = protocol


    def get_priority(self):
        return self._priority


    def set_priority(self, priority):
        self._priority = priority


    def get_handle(self):
        return self._handle


    def set_handle(self, handle):
        self._handle = handle


    def _get_tc_conf(self, netif):
        if self._tc_conf:
            return self._tc_conf
        self._tc_conf = dict()
        self._tc_conf[tcfilter.conf_device] = netif.get_name()
        self._tc_conf[tcfilter.conf_parent] = self._parent_qdisc.id()
        self._tc_conf[tcfilter.conf_type] = self.filtertype
        self._tc_conf[tcfilter.conf_protocol] = self._protocol
        self._tc_conf[tcfilter.conf_priotity] = self._priority
        self._tc_conf[tcfilter.conf_flowid] = (
            self._dest_qdisc.get_parent_class().id())
        return self._tc_conf


    def tc_cmd(self, tc_conf):
        print self._tc_cmd % tc_conf


    def setup(self, netif):
        pass


    def restore(self, netif):
        pass


class u32filter(tcfilter):

    filtertype = 'u32'

    def __init__(self):
        super(u32filter, self).__init__()
        self._rules = []


    def _filter_rules(self):
        return ' \\\n  '.join(self._rules)


    def add_rule(self, rule):
        self._rules.append(rule)


    def setup(self, netif):
        tc_conf = self._get_tc_conf(netif)
        tc_conf[tcfilter.conf_cmd] = 'add'
        tc_conf[tcfilter.conf_rules] = self._filter_rules()
        self.tc_cmd(tc_conf)


    def restore(self, netif):
        tc_conf = self._get_tc_conf(netif)
        tc_conf[tcfilter.conf_cmd] = 'del'
        tc_conf[tcfilter.conf_rules] = self._filter_rules()
        self.tc_cmd(tc_conf)

#TODO (ncrao): generate some typical rules: ack, syn, synack,
#              dport/sport, daddr/sddr, etc.
class qdisc(object):

    # tc command
    _tc_cmd = 'tc qdisc %(cmd)s dev %(dev)s %(parent)s ' \
              'handle %(qdiscid)s %(name)s %(params)s'

    def __init__(self, handle):
        self._handle = handle
        self._parent_class = None
        self._tc_conf = None


    def get_handle(self):
        return self._handle


    def get_parent_class(self):
        return self._parent_class


    def set_parent_class(self, parent_class):
        self._parent_class = parent_class


    def _get_tc_conf(self, netif):
        if self._tc_conf:
            return self._tc_conf
        self._tc_conf = dict()
        self._tc_conf[tcfilter.conf_device] = netif.get_name()
        if self._parent_class:
            self._tc_conf[tcfilter.conf_parent] = ('parent %s' %
                                                   self._parent_class.id())
        else:
            self._tc_conf[tcfilter.conf_parent] = 'root'
        self._tc_conf[tcfilter.conf_qdiscid] = self.id()
        self._tc_conf[tcfilter.conf_name] = self.name
        self._tc_conf[tcfilter.conf_params] = ''
        return self._tc_conf


    def id(self):
        return '%s:0' % self._handle


    def tc_cmd(self, tc_conf):
        print self._tc_cmd % tc_conf


    def setup(self, netif):
        tc_conf = self._get_tc_conf(netif)
        tc_conf[tcfilter.conf_command] = 'add'
        self.tc_cmd(tc_conf)


    def restore(self, netif):
        tc_conf = self._get_tc_conf(netif)
        tc_conf[tcfilter.conf_command] = 'del'
        self.tc_cmd(tc_conf)


class classful_qdisc(qdisc):

    classful = True

    def __init__(self, handle):
        super(classful_qdisc, self).__init__(handle)
        self._classes = []
        self._filters = []


    def add_class(self, child_class):
        self._classes.append(child_class)


    def add_filter(self, filter):
        filter.set_parent_qdisc(self)
        self._filters.append(filter)


    def setup(self, netif):
        super(classful_qdisc, self).setup(netif)

        # setup child classes
        for child in self._classes:
            child.setup(netif)

        # setup filters
        for filter in self._filters:
            filter.setup(netif)


    def restore(self, netif):
        # restore filters
        filters_copy = list(self._filters)
        filters_copy.reverse()
        for filter in filters_copy:
            filter.restore(netif)

        # restore child classes
        classes_copy = list(self._classes)
        classes_copy.reverse()
        for child in classes_copy:
            child.restore(netif)

        super(classful_qdisc, self).restore(netif)


class prio(classful_qdisc):

    name = 'prio'

    def __init__(self, handle=new_handle(), bands=3):
        super(prio, self).__init__(handle)
        self._bands = bands
        for counter in range(bands):
            self.add_class(tcclass(handle, counter + 1))


    def setup(self, netif):
        super(prio, self).setup(netif)


    def get_class(self, band):
        if band > self._bands:
            raise error.TestError('error inserting %s at band %s' % \
                                  (qdisc.name, band))
        return self._classes[band]


class classless_qdisc(qdisc):

    classful = False

    def __init__(self, handle):
        super(classless_qdisc, self).__init__(handle)


class pfifo(classless_qdisc):

    name = 'pfifo'

    def __init__(self, handle=new_handle()):
        super(pfifo, self).__init__(handle)


    def setup(self, netif):
        super(pfifo, self).setup(netif)


class netem(classless_qdisc):

    name = 'netem'

    def __init__(self, handle=new_handle()):
        super(netem, self).__init__(handle)
        self._params = list()


    def add_param(self, param):
        self._params.append(param)


    def setup(self, netif):
        super(netem, self).setup(netif)
        tc_conf = self._get_tc_conf(netif)
        tc_conf[tcfilter.conf_command] = 'change'
        tc_conf[tcfilter.conf_params] = ' '.join(self._params)
        self.tc_cmd(tc_conf)
