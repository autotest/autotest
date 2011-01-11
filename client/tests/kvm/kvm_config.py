#!/usr/bin/python
"""
KVM configuration file utility functions.

@copyright: Red Hat 2008-2010
"""

import logging, re, os, sys, optparse, array, traceback, cPickle
import common
import kvm_utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import logging_config, logging_manager


class config:
    """
    Parse an input file or string that follows the KVM Test Config File format
    and generate a list of dicts that will be later used as configuration
    parameters by the KVM tests.

    @see: http://www.linux-kvm.org/page/KVM-Autotest/Test_Config_File
    """

    def __init__(self, filename=None, debug=True):
        """
        Initialize the list and optionally parse a file.

        @param filename: Path of the file that will be taken.
        @param debug: Whether to turn on debugging output.
        """
        self.list = [array.array("H", [4, 4, 4, 4])]
        self.object_cache = []
        self.object_cache_indices = {}
        self.regex_cache = {}
        self.filename = filename
        self.debug = debug
        if filename:
            self.parse_file(filename)


    def parse_file(self, filename):
        """
        Parse file.  If it doesn't exist, raise an IOError.

        @param filename: Path of the configuration file.
        """
        if not os.path.exists(filename):
            raise IOError("File %s not found" % filename)
        self.filename = filename
        str = open(filename).read()
        self.list = self.parse(configreader(filename, str), self.list)


    def parse_string(self, str):
        """
        Parse a string.

        @param str: String to parse.
        """
        self.list = self.parse(configreader('<string>', str), self.list)


    def fork_and_parse(self, filename=None, str=None):
        """
        Parse a file and/or a string in a separate process to save memory.

        Python likes to keep memory to itself even after the objects occupying
        it have been destroyed.  If during a call to parse_file() or
        parse_string() a lot of memory is used, it can only be freed by
        terminating the process.  This function works around the problem by
        doing the parsing in a forked process and then terminating it, freeing
        any unneeded memory.

        Note: if an exception is raised during parsing, its information will be
        printed, and the resulting list will be empty.  The exception will not
        be raised in the process calling this function.

        @param filename: Path of file to parse (optional).
        @param str: String to parse (optional).
        """
        r, w = os.pipe()
        r, w = os.fdopen(r, "r"), os.fdopen(w, "w")
        pid = os.fork()
        if not pid:
            # Child process
            r.close()
            try:
                if filename:
                    self.parse_file(filename)
                if str:
                    self.parse_string(str)
            except:
                traceback.print_exc()
                self.list = []
            # Convert the arrays to strings before pickling because at least
            # some Python versions can't pickle/unpickle arrays
            l = [a.tostring() for a in self.list]
            cPickle.dump((l, self.object_cache), w, -1)
            w.close()
            os._exit(0)
        else:
            # Parent process
            w.close()
            (l, self.object_cache) = cPickle.load(r)
            r.close()
            os.waitpid(pid, 0)
            self.list = []
            for s in l:
                a = array.array("H")
                a.fromstring(s)
                self.list.append(a)


    def get_generator(self):
        """
        Generate dictionaries from the code parsed so far.  This should
        probably be called after parsing something.

        @return: A dict generator.
        """
        for a in self.list:
            name, shortname, depend, content = _array_get_all(a,
                                                              self.object_cache)
            dict = {"name": name, "shortname": shortname, "depend": depend}
            self._apply_content_to_dict(dict, content)
            yield dict


    def get_list(self):
        """
        Generate a list of dictionaries from the code parsed so far.
        This should probably be called after parsing something.

        @return: A list of dicts.
        """
        return list(self.get_generator())


    def count(self, filter=".*"):
        """
        Return the number of dictionaries whose names match filter.

        @param filter: A regular expression string.
        """
        exp = self._get_filter_regex(filter)
        count = 0
        for a in self.list:
            name = _array_get_name(a, self.object_cache)
            if exp.search(name):
                count += 1
        return count


    def parse_variants(self, cr, list, subvariants=False, prev_indent=-1):
        """
        Read and parse lines from a configreader object until a line with an
        indent level lower than or equal to prev_indent is encountered.

        @brief: Parse a 'variants' or 'subvariants' block from a configreader
            object.
        @param cr: configreader object to be parsed.
        @param list: List of arrays to operate on.
        @param subvariants: If True, parse in 'subvariants' mode;
            otherwise parse in 'variants' mode.
        @param prev_indent: The indent level of the "parent" block.
        @return: The resulting list of arrays.
        """
        new_list = []

        while True:
            pos = cr.tell()
            (indented_line, line, indent) = cr.get_next_line()
            if indent <= prev_indent:
                cr.seek(pos)
                break

            # Get name and dependencies
            (name, depend) = map(str.strip, line.lstrip("- ").split(":"))

            # See if name should be added to the 'shortname' field
            add_to_shortname = not name.startswith("@")
            name = name.lstrip("@")

            # Store name and dependencies in cache and get their indices
            n = self._store_str(name)
            d = self._store_str(depend)

            # Make a copy of list
            temp_list = [a[:] for a in list]

            if subvariants:
                # If we're parsing 'subvariants', first modify the list
                if add_to_shortname:
                    for a in temp_list:
                        _array_append_to_name_shortname_depend(a, n, d)
                else:
                    for a in temp_list:
                        _array_append_to_name_depend(a, n, d)
                temp_list = self.parse(cr, temp_list, restricted=True,
                                       prev_indent=indent)
            else:
                # If we're parsing 'variants', parse before modifying the list
                if self.debug:
                    _debug_print(indented_line,
                                 "Entering variant '%s' "
                                 "(variant inherits %d dicts)" %
                                 (name, len(list)))
                temp_list = self.parse(cr, temp_list, restricted=False,
                                       prev_indent=indent)
                if add_to_shortname:
                    for a in temp_list:
                        _array_prepend_to_name_shortname_depend(a, n, d)
                else:
                    for a in temp_list:
                        _array_prepend_to_name_depend(a, n, d)

            new_list += temp_list

        return new_list


    def parse(self, cr, list, restricted=False, prev_indent=-1):
        """
        Read and parse lines from a configreader object until a line with an
        indent level lower than or equal to prev_indent is encountered.

        @brief: Parse a configreader object.
        @param cr: A configreader object.
        @param list: A list of arrays to operate on (list is modified in
            place and should not be used after the call).
        @param restricted: If True, operate in restricted mode
            (prohibit 'variants').
        @param prev_indent: The indent level of the "parent" block.
        @return: The resulting list of arrays.
        @note: List is destroyed and should not be used after the call.
            Only the returned list should be used.
        """
        current_block = ""

        while True:
            pos = cr.tell()
            (indented_line, line, indent) = cr.get_next_line()
            if indent <= prev_indent:
                cr.seek(pos)
                self._append_content_to_arrays(list, current_block)
                break

            len_list = len(list)

            # Parse assignment operators (keep lines in temporary buffer)
            if "=" in line:
                if self.debug and not restricted:
                    _debug_print(indented_line,
                                 "Parsing operator (%d dicts in current "
                                 "context)" % len_list)
                current_block += line + "\n"
                continue

            # Flush the temporary buffer
            self._append_content_to_arrays(list, current_block)
            current_block = ""

            words = line.split()

            # Parse 'no' and 'only' statements
            if words[0] == "no" or words[0] == "only":
                if len(words) <= 1:
                    continue
                filters = map(self._get_filter_regex, words[1:])
                filtered_list = []
                if words[0] == "no":
                    for a in list:
                        name = _array_get_name(a, self.object_cache)
                        for filter in filters:
                            if filter.search(name):
                                break
                        else:
                            filtered_list.append(a)
                if words[0] == "only":
                    for a in list:
                        name = _array_get_name(a, self.object_cache)
                        for filter in filters:
                            if filter.search(name):
                                filtered_list.append(a)
                                break
                list = filtered_list
                if self.debug and not restricted:
                    _debug_print(indented_line,
                                 "Parsing no/only (%d dicts in current "
                                 "context, %d remain)" %
                                 (len_list, len(list)))
                continue

            # Parse 'variants'
            if line == "variants:":
                # 'variants' not allowed in restricted mode
                # (inside an exception or inside subvariants)
                if restricted:
                    e_msg = "Using variants in this context is not allowed"
                    cr.raise_error(e_msg)
                if self.debug and not restricted:
                    _debug_print(indented_line,
                                 "Entering variants block (%d dicts in "
                                 "current context)" % len_list)
                list = self.parse_variants(cr, list, subvariants=False,
                                           prev_indent=indent)
                continue

            # Parse 'subvariants' (the block is parsed for each dict
            # separately)
            if line == "subvariants:":
                if self.debug and not restricted:
                    _debug_print(indented_line,
                                 "Entering subvariants block (%d dicts in "
                                 "current context)" % len_list)
                new_list = []
                # Remember current position
                pos = cr.tell()
                # Read the lines in any case
                self.parse_variants(cr, [], subvariants=True,
                                    prev_indent=indent)
                # Iterate over the list...
                for index in xrange(len(list)):
                    # Revert to initial position in this 'subvariants' block
                    cr.seek(pos)
                    # Everything inside 'subvariants' should be parsed in
                    # restricted mode
                    new_list += self.parse_variants(cr, list[index:index+1],
                                                    subvariants=True,
                                                    prev_indent=indent)
                list = new_list
                continue

            # Parse 'include' statements
            if words[0] == "include":
                if len(words) <= 1:
                    continue
                if self.debug and not restricted:
                    _debug_print(indented_line, "Entering file %s" % words[1])
                if self.filename:
                    filename = os.path.join(os.path.dirname(self.filename),
                                            words[1])
                    if os.path.exists(filename):
                        str = open(filename).read()
                        list = self.parse(configreader(filename, str), list, restricted)
                        if self.debug and not restricted:
                            _debug_print("", "Leaving file %s" % words[1])
                    else:
                        logging.warning("Cannot include %s -- file not found",
                                        filename)
                else:
                    logging.warning("Cannot include %s because no file is "
                                    "currently open", words[1])
                continue

            # Parse multi-line exceptions
            # (the block is parsed for each dict separately)
            if line.endswith(":"):
                if self.debug and not restricted:
                    _debug_print(indented_line,
                                 "Entering multi-line exception block "
                                 "(%d dicts in current context outside "
                                 "exception)" % len_list)
                line = line[:-1]
                new_list = []
                # Remember current position
                pos = cr.tell()
                # Read the lines in any case
                self.parse(cr, [], restricted=True, prev_indent=indent)
                # Iterate over the list...
                exp = self._get_filter_regex(line)
                for index in xrange(len(list)):
                    name = _array_get_name(list[index], self.object_cache)
                    if exp.search(name):
                        # Revert to initial position in this exception block
                        cr.seek(pos)
                        # Everything inside an exception should be parsed in
                        # restricted mode
                        new_list += self.parse(cr, list[index:index+1],
                                               restricted=True,
                                               prev_indent=indent)
                    else:
                        new_list.append(list[index])
                list = new_list
                continue

        return list


    def _get_filter_regex(self, filter):
        """
        Return a regex object corresponding to a given filter string.

        All regular expressions given to the parser are passed through this
        function first.  Its purpose is to make them more specific and better
        suited to match dictionary names: it forces simple expressions to match
        only between dots or at the beginning or end of a string.  For example,
        the filter 'foo' will match 'foo.bar' but not 'foobar'.
        """
        try:
            return self.regex_cache[filter]
        except KeyError:
            exp = re.compile(r"(\.|^)(%s)(\.|$)" % filter)
            self.regex_cache[filter] = exp
            return exp


    def _store_str(self, str):
        """
        Store str in the internal object cache, if it isn't already there, and
        return its identifying index.

        @param str: String to store.
        @return: The index of str in the object cache.
        """
        try:
            return self.object_cache_indices[str]
        except KeyError:
            self.object_cache.append(str)
            index = len(self.object_cache) - 1
            self.object_cache_indices[str] = index
            return index


    def _append_content_to_arrays(self, list, content):
        """
        Append content (config code containing assignment operations) to a list
        of arrays.

        @param list: List of arrays to operate on.
        @param content: String containing assignment operations.
        """
        if content:
            str_index = self._store_str(content)
            for a in list:
                _array_append_to_content(a, str_index)


    def _apply_content_to_dict(self, dict, content):
        """
        Apply the operations in content (config code containing assignment
        operations) to a dict.

        @param dict: Dictionary to operate on.  Must have 'name' key.
        @param content: String containing assignment operations.
        """
        for line in content.splitlines():
            op_found = None
            op_pos = len(line)
            for op in ops:
                pos = line.find(op)
                if pos >= 0 and pos < op_pos:
                    op_found = op
                    op_pos = pos
            if not op_found:
                continue
            (left, value) = map(str.strip, line.split(op_found, 1))
            if value and ((value[0] == '"' and value[-1] == '"') or
                          (value[0] == "'" and value[-1] == "'")):
                value = value[1:-1]
            filters_and_key = map(str.strip, left.split(":"))
            filters = filters_and_key[:-1]
            key = filters_and_key[-1]
            for filter in filters:
                exp = self._get_filter_regex(filter)
                if not exp.search(dict["name"]):
                    break
            else:
                ops[op_found](dict, key, value)


# Assignment operators

def _op_set(dict, key, value):
    dict[key] = value


def _op_append(dict, key, value):
    dict[key] = dict.get(key, "") + value


def _op_prepend(dict, key, value):
    dict[key] = value + dict.get(key, "")


def _op_regex_set(dict, exp, value):
    exp = re.compile("^(%s)$" % exp)
    for key in dict:
        if exp.match(key):
            dict[key] = value


def _op_regex_append(dict, exp, value):
    exp = re.compile("^(%s)$" % exp)
    for key in dict:
        if exp.match(key):
            dict[key] += value


def _op_regex_prepend(dict, exp, value):
    exp = re.compile("^(%s)$" % exp)
    for key in dict:
        if exp.match(key):
            dict[key] = value + dict[key]


ops = {
    "=": _op_set,
    "+=": _op_append,
    "<=": _op_prepend,
    "?=": _op_regex_set,
    "?+=": _op_regex_append,
    "?<=": _op_regex_prepend,
}


# Misc functions

def _debug_print(str1, str2=""):
    """
    Nicely print two strings and an arrow.

    @param str1: First string.
    @param str2: Second string.
    """
    if str2:
        str = "%-50s ---> %s" % (str1, str2)
    else:
        str = str1
    logging.debug(str)


# configreader

class configreader:
    """
    Preprocess an input string and provide file-like services.
    This is intended as a replacement for the file and StringIO classes,
    whose readline() and/or seek() methods seem to be slow.
    """

    def __init__(self, filename, str):
        """
        Initialize the reader.

        @param str: The string to parse.
        """
        self.filename = filename
        self.line_index = 0
        self.lines = []
        self.real_number = []
        for num, line in enumerate(str.splitlines()):
            line = line.rstrip().expandtabs()
            stripped_line = line.strip()
            indent = len(line) - len(stripped_line)
            if (not stripped_line
                or stripped_line.startswith("#")
                or stripped_line.startswith("//")):
                continue
            self.lines.append((line, stripped_line, indent))
            self.real_number.append(num + 1)


    def get_next_line(self):
        """
        Get the next non-empty, non-comment line in the string.

        @param file: File like object.
        @return: (line, stripped_line, indent), where indent is the line's
            indent level or -1 if no line is available.
        """
        try:
            if self.line_index < len(self.lines):
                return self.lines[self.line_index]
            else:
                return (None, None, -1)
        finally:
            self.line_index += 1


    def tell(self):
        """
        Return the current line index.
        """
        return self.line_index


    def seek(self, index):
        """
        Set the current line index.
        """
        self.line_index = index

    def raise_error(self, msg):
        """Raise an error related to the last line returned by get_next_line()
        """
        if self.line_index == 0: # nothing was read. shouldn't happen, but...
            line_id = 'BEGIN'
        elif self.line_index >= len(self.lines): # past EOF
            line_id = 'EOF'
        else:
            # line_index is the _next_ line. get the previous one
            line_id = str(self.real_number[self.line_index-1])
        raise error.AutotestError("%s:%s: %s" % (self.filename, line_id, msg))


# Array structure:
# ----------------
# The first 4 elements contain the indices of the 4 segments.
# a[0] -- Index of beginning of 'name' segment (always 4).
# a[1] -- Index of beginning of 'shortname' segment.
# a[2] -- Index of beginning of 'depend' segment.
# a[3] -- Index of beginning of 'content' segment.
# The next elements in the array comprise the aforementioned segments:
# The 'name' segment begins with a[a[0]] and ends with a[a[1]-1].
# The 'shortname' segment begins with a[a[1]] and ends with a[a[2]-1].
# The 'depend' segment begins with a[a[2]] and ends with a[a[3]-1].
# The 'content' segment begins with a[a[3]] and ends at the end of the array.

# The following functions append/prepend to various segments of an array.

def _array_append_to_name_shortname_depend(a, name, depend):
    a.insert(a[1], name)
    a.insert(a[2] + 1, name)
    a.insert(a[3] + 2, depend)
    a[1] += 1
    a[2] += 2
    a[3] += 3


def _array_prepend_to_name_shortname_depend(a, name, depend):
    a[1] += 1
    a[2] += 2
    a[3] += 3
    a.insert(a[0], name)
    a.insert(a[1], name)
    a.insert(a[2], depend)


def _array_append_to_name_depend(a, name, depend):
    a.insert(a[1], name)
    a.insert(a[3] + 1, depend)
    a[1] += 1
    a[2] += 1
    a[3] += 2


def _array_prepend_to_name_depend(a, name, depend):
    a[1] += 1
    a[2] += 1
    a[3] += 2
    a.insert(a[0], name)
    a.insert(a[2], depend)


def _array_append_to_content(a, content):
    a.append(content)


def _array_get_name(a, object_cache):
    """
    Return the name of a dictionary represented by a given array.

    @param a: Array representing a dictionary.
    @param object_cache: A list of strings referenced by elements in the array.
    """
    return ".".join([object_cache[i] for i in a[a[0]:a[1]]])


def _array_get_all(a, object_cache):
    """
    Return a 4-tuple containing all the data stored in a given array, in a
    format that is easy to turn into an actual dictionary.

    @param a: Array representing a dictionary.
    @param object_cache: A list of strings referenced by elements in the array.
    @return: A 4-tuple: (name, shortname, depend, content), in which all
        members are strings except depend which is a list of strings.
    """
    name = ".".join([object_cache[i] for i in a[a[0]:a[1]]])
    shortname = ".".join([object_cache[i] for i in a[a[1]:a[2]]])
    content = "".join([object_cache[i] for i in a[a[3]:]])
    depend = []
    prefix = ""
    for n, d in zip(a[a[0]:a[1]], a[a[2]:a[3]]):
        for dep in object_cache[d].split():
            depend.append(prefix + dep)
        prefix += object_cache[n] + "."
    return name, shortname, depend, content


if __name__ == "__main__":
    parser = optparse.OptionParser("usage: %prog [options] [filename]")
    parser.add_option('--verbose', dest="debug", action='store_true',
                      help='include debug messages in console output')

    options, args = parser.parse_args()
    debug = options.debug
    if args:
        filenames = args
    else:
        filenames = [os.path.join(os.path.dirname(sys.argv[0]), "tests.cfg")]

    # Here we configure the stand alone program to use the autotest
    # logging system.
    logging_manager.configure_logging(kvm_utils.KvmLoggingConfig(),
                                      verbose=debug)
    cfg = config(debug=debug)
    for fn in filenames:
        cfg.parse_file(fn)
    dicts = cfg.get_generator()
    for i, dict in enumerate(dicts):
        print "Dictionary #%d:" % (i)
        keys = dict.keys()
        keys.sort()
        for key in keys:
            print "    %s = %s" % (key, dict[key])
