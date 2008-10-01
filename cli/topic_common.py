#
# Copyright 2008 Google Inc. All Rights Reserved.
#
"""
This module contains the generic CLI object

High Level Design:

The atest class contains attributes & method generic to all the CLI
operations.

The class inheritance is shown here using the command
'atest host create ...' as an example:

atest <-- host <-- host_create <-- site_host_create

Note: The site_<topic>.py and its classes are only needed if you need
to override the common <topic>.py methods with your site specific ones.


High Level Algorithm:

1. atest figures out the topic and action from the 2 first arguments
   on the command line and imports the <topic> (or site_<topic>)
   module.

1. Init
   The main atest module creates a <topic>_<action> object.  The
   __init__() function is used to setup the parser options, if this
   <action> has some specific options to add to its <topic>.

   If it exists, the child __init__() method must call its parent
   class __init__() before adding its own parser arguments.

2. Parsing
   If the child wants to validate the parsing (e.g. make sure that
   there are hosts in the arguments), or if it wants to check the
   options it added in its __init__(), it should implement a parse()
   method.

   The child parser must call its parent parser and gets back the
   options dictionary and the rest of the command line arguments
   (leftover). Each level gets to see all the options, but the
   leftovers can be deleted as they can be consumed by only one
   object.

3. Execution
   This execute() method is specific to the child and should use the
   self.execute_rpc() to send commands to the Autotest Front-End.  It
   should return results.

4. Output
   The child output() method is called with the execute() resutls as a
   parameter.  This is child-specific, but should leverage the
   atest.print_*() methods.
"""

import os, sys, pwd, optparse, re, textwrap, urllib2, getpass, socket
from autotest_lib.cli import rpc
from autotest_lib.frontend.afe.json_rpc import proxy


# Maps the AFE keys to printable names.
KEYS_TO_NAMES_EN = {'hostname': 'Host',
                    'platform': 'Platform',
                    'status': 'Status',
                    'locked': 'Locked',
                    'locked_by': 'Locked by',
                    'labels': 'Labels',
                    'description': 'Description',
                    'hosts': 'Hosts',
                    'users': 'Users',
                    'id': 'Id',
                    'name': 'Name',
                    'invalid': 'Valid',
                    'login': 'Login',
                    'access_level': 'Access Level',
                    'job_id': 'Job Id',
                    'job_owner': 'Job Owner',
                    'job_name': 'Job Name',
                    'test_type': 'Test Type',
                    'test_class': 'Test Class',
                    'path': 'Path',
                    'owner': 'Owner',
                    'status_counts': 'Status Counts',
                    'hosts_status': 'Host Status',
                    'priority': 'Priority',
                    'control_type': 'Control Type',
                    'created_on': 'Created On',
                    'synch_type': 'Synch Type',
                    'control_file': 'Control File',
                    'only_if_needed': 'Use only if needed',
                    }

# In the failure, tag that will replace the item.
FAIL_TAG = '<XYZ>'

# Global socket timeout 
DEFAULT_SOCKET_TIMEOUT = 5
# For list commands, can take longer
LIST_SOCKET_TIMEOUT = 30
# For uploading kernels, can take much, much longer
UPLOAD_SOCKET_TIMEOUT = 60*30


# Convertion functions to be called for printing,
# e.g. to print True/False for booleans.
def __convert_platform(field):
    if not field:
        # Can be None
        return ""
    elif type(field) == int:
        # Can be 0/1 for False/True
        return str(bool(field))
    else:
        # Can be a platform name
        return field


def _int_2_bool_string(value):
    return str(bool(value))

KEYS_CONVERT = {'locked': _int_2_bool_string,
                'invalid': lambda flag: str(bool(not flag)),
                'only_if_needed': _int_2_bool_string,
                'platform': __convert_platform,
                'labels': lambda labels: ', '.join(labels)}

class CliError(Exception):
    pass


class atest(object):
    """Common class for generic processing
    Should only be instantiated by itself for usage
    references, otherwise, the <topic> objects should
    be used."""
    msg_topic = "[acl|host|job|label|test|user]"
    usage_action = "[action]"
    msg_items = ''

    def invalid_arg(self, header, follow_up=''):
        twrap = textwrap.TextWrapper(initial_indent='        ',
                                     subsequent_indent='       ')
        rest = twrap.fill(follow_up)

        if self.kill_on_failure:
            self.invalid_syntax(header + rest)
        else:
            print >> sys.stderr, header + rest


    def invalid_syntax(self, msg):
        print
        print >> sys.stderr, msg
        print
        print "usage:",
        print self._get_usage()
        print
        sys.exit(1)


    def generic_error(self, msg):
        print >> sys.stderr, msg
        sys.exit(1)


    def failure(self, full_error, item=None, what_failed=''):
        """If kill_on_failure, print this error and die,
        otherwise, queue the error and accumulate all the items
        that triggered the same error."""

        if self.debug:
            errmsg = str(full_error)
        else:
            errmsg = str(full_error).split('Traceback')[0].rstrip('\n')

        if self.kill_on_failure:
            print >> sys.stderr, "%s\n    %s" % (what_failed, errmsg)
            sys.exit(1)

        # Build a dictionary with the 'what_failed' as keys.  The
        # values are dictionaries with the errmsg as keys and a set
        # of items as values.
        # self.failed = 
        # {'Operation delete_host_failed': {'AclAccessViolation:
        #                                        set('host0', 'host1')}}
        # Try to gather all the same error messages together,
        # even if they contain the 'item'
        if item and item in errmsg:
            errmsg = errmsg.replace(item, FAIL_TAG)
        if self.failed.has_key(what_failed):
            self.failed[what_failed].setdefault(errmsg, set()).add(item)
        else:
            self.failed[what_failed] = {errmsg: set([item])}


    def show_all_failures(self):
        if not self.failed:
            return 0
        for what_failed in self.failed.keys():
            print >> sys.stderr, what_failed + ':'
            for (errmsg, items) in self.failed[what_failed].iteritems():
                if len(items) == 0:
                    print >> sys.stderr, errmsg
                elif items == set(['']):
                    print >> sys.stderr, '    ' + errmsg
                elif len(items) == 1:
                    # Restore the only item
                    if FAIL_TAG in errmsg:
                        errmsg = errmsg.replace(FAIL_TAG, items.pop())
                    else:
                        errmsg = '%s (%s)' % (errmsg, items.pop())
                    print >> sys.stderr, '    ' + errmsg
                else:
                    print >> sys.stderr, '    ' + errmsg + ' with <XYZ> in:'
                    twrap = textwrap.TextWrapper(initial_indent='        ',
                                                 subsequent_indent='        ')
                    items = list(items)
                    items.sort()
                    print >> sys.stderr, twrap.fill(', '.join(items))
        return 1


    def __init__(self):
        """Setup the parser common options"""
        # Initialized for unit tests.
        self.afe = None
        self.failed = {}
        self.data = {}
        self.debug = False
        self.kill_on_failure = False
        self.web_server = ''
        self.verbose = False

        self.parser = optparse.OptionParser(self._get_usage())
        self.parser.add_option('-g', '--debug',
                               help='Print debugging information',
                               action='store_true', default=False)
        self.parser.add_option('--kill-on-failure',
                               help='Stop at the first failure',
                               action='store_true', default=False)
        self.parser.add_option('--parse',
                               help='Print the output using colon '
                               'separated key=value fields',
                               action='store_true', default=False)
        self.parser.add_option('-v', '--verbose',
                               action='store_true', default=False)
        self.parser.add_option('-w', '--web',
                               help='Specify the autotest server '
                               'to talk to',
                               action='store', type='string',
                               dest='web_server', default=None)

        # Shorten the TCP timeout.
        socket.setdefaulttimeout(DEFAULT_SOCKET_TIMEOUT)


    def _file_list(self, options, opt_file='', opt_list='', add_on=[]):
        """Returns a list containing the unique items from the
        options.<opt_list>, from the file options.<opt_file>,
        and from the space separated add_on strings.
        The opt_list can be space or comma separated list.
        Used for host, acls, labels... arguments"""
        def __get_items(string, split_on='[\s,]\s*'):
            return [item.strip() for item in re.split(split_on, string)
                    if item]

        # Start with the add_on
        result = set()
        for items in add_on:
            # Don't split on space here because the add-on
            # may have some spaces (like the job name)
            #result.update(item.strip() for item in items.split(',') if item)
            result.update(__get_items(items, split_on='[,]'))

        # Process the opt_list, if any
        try:
            items = getattr(options, opt_list)
            result.update(__get_items(items))
        except (AttributeError, TypeError):
            pass

        # Process the file list, if any and not empty
        # The file can contain space and/or comma separated items
        try:
            flist = getattr(options, opt_file)
            file_content = []
            for line in open(flist).readlines():
                file_content += __get_items(line)
            if len(file_content) == 0:
                self.invalid_syntax("Empty file %s" % flist)
            result.update(file_content)
        except (AttributeError, TypeError):
            pass
        except IOError:
            self.invalid_syntax("Could not open file %s" % flist)

        return list(result)


    def _get_usage(self):
        return "atest %s %s [options] %s" % (self.msg_topic.lower(),
                                             self.usage_action,
                                             self.msg_items)


    def parse_with_flist(self, flists, req_items):
        """Flists is a list of tuples containing:
        (attribute, opt_fname, opt_list, use_leftover)

        self.<atttribute> will be populated with a set
        containing the lines of the file named
        options.<opt_fname> and the options.<opt_list> values
        and the leftover from the parsing if use_leftover is
        True.  There should only be one use_leftover set to
        True in the list.
        Also check if the req_items is not empty after parsing."""
        (options, leftover) = atest.parse(self)
        if leftover == None:
            leftover = []

        for (attribute, opt_fname, opt_list, use_leftover) in flists:
            if use_leftover:
                add_on = leftover
                leftover = []
            else:
                add_on = []

            setattr(self, attribute,
                    self._file_list(options,
                                    opt_file=opt_fname,
                                    opt_list=opt_list,
                                    add_on=add_on))

        if (req_items and not getattr(self, req_items, None)):
            self.invalid_syntax('%s %s requires at least one %s' %
                                (self.msg_topic,
                                 self.usage_action,
                                 self.msg_topic))

        return (options, leftover)


    def parse(self):
        """Parse all the arguments.

        It consumes what the common object needs to know, and
        let the children look at all the options.  We could
        remove the options that we have used, but there is no
        harm in leaving them, and the children may need them
        in the future.

        Must be called from its children parse()"""
        (options, leftover) = self.parser.parse_args()
        # Handle our own options setup in __init__()
        self.debug = options.debug
        self.kill_on_failure = options.kill_on_failure

        if options.parse:
            suffix = '_parse'
        else:
            suffix = '_std'
        for func in ['print_fields', 'print_table',
                     'print_by_ids']:
            setattr(self, func, getattr(self, func + suffix))

        self.verbose = options.verbose
        self.web_server = options.web_server
        self.afe = rpc.afe_comm(self.web_server)

        return (options, leftover)


    def check_and_create_items(self, op_get, op_create,
                                items, **data_create):
        """Create the items if they don't exist already"""
        for item in items:
            ret = self.execute_rpc(op_get, name=item)

            if len(ret) == 0:
                try:
                    data_create['name'] = item
                    self.execute_rpc(op_create, **data_create)
                except CliError:
                    continue


    def execute_rpc(self, op, item='', **data):
        retry = 2
        while retry:
            try:
                return self.afe.run(op, **data)
            except urllib2.URLError, err:
                if 'timed out' not in err.reason:
                    self.invalid_syntax('Invalid server name %s: %s' %
                                        (self.afe.web_server, err))
                if self.debug:
                    print 'retrying: %r %d' % (data, retry)
                retry -= 1
                if retry == 0:
                    if item:
                        myerr = '%s timed out for %s' % (op, item)
                    else:
                        myerr = '%s timed out' % op
                    self.failure(myerr, item=item,
                                 what_failed=("Timed-out contacting "
                                              "the Autotest server"))
                    raise CliError("Timed-out contacting the Autotest server")
            except Exception, full_error:
                # There are various exceptions throwns by JSON,
                # urllib & httplib, so catch them all.
                self.failure(full_error, item=item,
                             what_failed='Operation %s failed' % op)
                raise CliError(str(full_error))


    # There is no output() method in the atest object (yet?)
    # but here are some helper functions to be used by its
    # children
    def print_wrapped(self, msg, values):
        if len(values) == 0:
            return
        elif len(values) == 1:
            print msg + ': '
        elif len(values) > 1:
            if msg.endswith('s'):
                print msg + ': '
            else:
                print msg + 's: '

        values.sort()
        twrap = textwrap.TextWrapper(initial_indent='\t',
                                     subsequent_indent='\t')
        print twrap.fill(', '.join(values))


    def __conv_value(self, type, value):
        return KEYS_CONVERT.get(type, str)(value)


    def print_fields_std(self, items, keys, title=None):
        """Print the keys in each item, one on each line"""
        if not items:
            print "No results"
            return
        if title:
            print title
        for item in items:
            for key in keys:
                print '%s: %s' % (KEYS_TO_NAMES_EN[key],
                                  self.__conv_value(key,
                                                    item[key]))


    def print_fields_parse(self, items, keys, title=None):
        """Print the keys in each item as comma
        separated name=value"""
        if not items:
            print "No results"
            return
        for item in items:
            values = ['%s=%s' % (KEYS_TO_NAMES_EN[key],
                                  self.__conv_value(key,
                                                    item[key]))
                      for key in keys
                      if self.__conv_value(key,
                                           item[key]) != '']
            print ':'.join(values)


    def __find_justified_fmt(self, items, keys):
        """Find the max length for each field."""
        lens = {}
        # Don't justify the last field, otherwise we have blank
        # lines when the max is overlaps but the current values
        # are smaller
        if not items:
            print "No results"
            return
        for key in keys[:-1]:
            lens[key] = max(len(self.__conv_value(key,
                                                  item[key]))
                            for item in items)
            lens[key] = max(lens[key], len(KEYS_TO_NAMES_EN[key]))
        lens[keys[-1]] = 0

        return '  '.join(["%%-%ds" % lens[key] for key in keys])


    def print_table_std(self, items, keys_header, sublist_keys={}):
        """Print a mix of header and lists in a user readable
        format
        The headers are justified, the sublist_keys are wrapped."""
        if not items:
            print "No results"
            return
        fmt = self.__find_justified_fmt(items, keys_header)
        header = tuple(KEYS_TO_NAMES_EN[key] for key in keys_header)
        print fmt % header
        for item in items:
            values = tuple(self.__conv_value(key, item[key])
                           for key in keys_header)
            print fmt % values
            if self.verbose and sublist_keys:
                for key in sublist_keys:
                    self.print_wrapped(KEYS_TO_NAMES_EN[key],
                                       item[key])
                print '\n'


    def print_table_parse(self, items, keys_header, sublist_keys=[]):
        """Print a mix of header and lists in a user readable
        format"""
        if not items:
            print "No results"
            return
        for item in items:
            values = ['%s=%s' % (KEYS_TO_NAMES_EN[key],
                                 self.__conv_value(key, item[key]))
                      for key in keys_header
                      if self.__conv_value(key,
                                           item[key]) != '']

            if self.verbose:
                [values.append('%s=%s'% (KEYS_TO_NAMES_EN[key],
                                         ','.join(item[key])))
                 for key in sublist_keys
                 if len(item[key])]

            print ':'.join(values)


    def print_by_ids_std(self, items, title=None, line_before=False):
        """Prints ID & names of items in a user readable form"""
        if not items:
            return
        if line_before:
            print
        if title:
            print title + ':'
        self.print_table_std(items, keys_header=['id', 'name'])


    def print_by_ids_parse(self, items, title=None, line_before=False):
        """Prints ID & names of items in a parseable format"""
        if not items:
            print "No results"
            return
        if title:
            print title + '=',
        values = []
        for item in items:
            values += ['%s=%s' % (KEYS_TO_NAMES_EN[key],
                                  self.__conv_value(key,
                                                    item[key]))
                       for key in ['id', 'name']
                       if self.__conv_value(key,
                                            item[key]) != '']
        print ':'.join(values)
