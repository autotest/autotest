#!/usr/bin/python
"""
KVM configuration file utility functions.

@copyright: Red Hat 2008-2009
"""

import logging, re, os, sys, StringIO, optparse
import common
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import logging_config, logging_manager


class KvmLoggingConfig(logging_config.LoggingConfig):
    def configure_logging(self, results_dir=None, verbose=False):
        super(KvmLoggingConfig, self).configure_logging(use_console=True,
                                                        verbose=verbose)


class config:
    """
    Parse an input file or string that follows the KVM Test Config File format
    and generate a list of dicts that will be later used as configuration
    parameters by the the KVM tests.

    @see: http://www.linux-kvm.org/page/KVM-Autotest/Test_Config_File
    """

    def __init__(self, filename=None, debug=False):
        """
        Initialize the list and optionally parse filename.

        @param filename: Path of the file that will be taken.
        @param debug: Whether to turn debugging output.
        """
        self.list = [{"name": "", "shortname": "", "depend": []}]
        self.debug = debug
        self.filename = filename
        if filename:
            self.parse_file(filename)


    def parse_file(self, filename):
        """
        Parse filename, return the resulting list and store it in .list. If
        filename does not exist, raise an exception.

        @param filename: Path of the configuration file.
        """
        if not os.path.exists(filename):
            raise Exception, "File %s not found" % filename
        self.filename = filename
        file = open(filename, "r")
        self.list = self.parse(file, self.list)
        file.close()
        return self.list


    def parse_string(self, str):
        """
        Parse a string, return the resulting list and store it in .list.

        @param str: String that will be parsed.
        """
        file = StringIO.StringIO(str)
        self.list = self.parse(file, self.list)
        file.close()
        return self.list


    def get_list(self):
        """
        Return the list of dictionaries. This should probably be called after
        parsing something.
        """
        return self.list


    def match(self, filter, dict):
        """
        Return True if dict matches filter.

        @param filter: A regular expression that defines the filter.
        @param dict: Dictionary that will be inspected.
        """
        filter = re.compile(r"(\.|^)" + filter + r"(\.|$)")
        return bool(filter.search(dict["name"]))


    def filter(self, filter, list=None):
        """
        Filter a list of dicts.

        @param filter: A regular expression that will be used as a filter.
        @param list: A list of dictionaries that will be filtered.
        """
        if list is None:
            list = self.list
        return [dict for dict in list if self.match(filter, dict)]


    def split_and_strip(self, str, sep="="):
        """
        Split str and strip quotes from the resulting parts.

        @param str: String that will be processed
        @param sep: Separator that will be used to split the string
        """
        temp = str.split(sep, 1)
        for i in range(len(temp)):
            temp[i] = temp[i].strip()
            if re.findall("^\".*\"$", temp[i]):
                temp[i] = temp[i].strip("\"")
            elif re.findall("^\'.*\'$", temp[i]):
                temp[i] = temp[i].strip("\'")
        return temp


    def get_next_line(self, file):
        """
        Get the next non-empty, non-comment line in a file like object.

        @param file: File like object
        @return: If no line is available, return None.
        """
        while True:
            line = file.readline()
            if line == "": return None
            stripped_line = line.strip()
            if len(stripped_line) > 0 \
                    and not stripped_line.startswith('#') \
                    and not stripped_line.startswith('//'):
                return line


    def get_next_line_indent(self, file):
        """
        Return the indent level of the next non-empty, non-comment line in file.

        @param file: File like object.
        @return: If no line is available, return -1.
        """
        pos = file.tell()
        line = self.get_next_line(file)
        if not line:
            file.seek(pos)
            return -1
        line = line.expandtabs()
        indent = 0
        while line[indent] == ' ':
            indent += 1
        file.seek(pos)
        return indent


    def add_name(self, str, name, append=False):
        """
        Add name to str with a separator dot and return the result.

        @param str: String that will be processed
        @param name: name that will be appended to the string.
        @return: If append is True, append name to str.
                Otherwise, pre-pend name to str.
        """
        if str == "":
            return name
        # Append?
        elif append:
            return str + "." + name
        # Prepend?
        else:
            return name + "." + str


    def parse_variants(self, file, list, subvariants=False, prev_indent=-1):
        """
        Read and parse lines from file like object until a line with an indent
        level lower than or equal to prev_indent is encountered.

        @brief: Parse a 'variants' or 'subvariants' block from a file-like
        object.
        @param file: File-like object that will be parsed
        @param list: List of dicts to operate on
        @param subvariants: If True, parse in 'subvariants' mode;
        otherwise parse in 'variants' mode
        @param prev_indent: The indent level of the "parent" block
        @return: The resulting list of dicts.
        """
        new_list = []

        while True:
            indent = self.get_next_line_indent(file)
            if indent <= prev_indent:
                break
            indented_line = self.get_next_line(file).rstrip()
            line = indented_line.strip()

            # Get name and dependencies
            temp = line.strip("- ").split(":")
            name = temp[0]
            if len(temp) == 1:
                dep_list = []
            else:
                dep_list = temp[1].split()

            # See if name should be added to the 'shortname' field
            add_to_shortname = True
            if name.startswith("@"):
                name = name.strip("@")
                add_to_shortname = False

            # Make a deep copy of list
            temp_list = []
            for dict in list:
                new_dict = dict.copy()
                new_dict["depend"] = dict["depend"][:]
                temp_list.append(new_dict)

            if subvariants:
                # If we're parsing 'subvariants', first modify the list
                self.__modify_list_subvariants(temp_list, name, dep_list,
                                               add_to_shortname)
                temp_list = self.parse(file, temp_list,
                        restricted=True, prev_indent=indent)
            else:
                # If we're parsing 'variants', parse before modifying the list
                if self.debug:
                    self.__debug_print(indented_line,
                                       "Entering variant '%s' "
                                       "(variant inherits %d dicts)" %
                                       (name, len(list)))
                temp_list = self.parse(file, temp_list,
                        restricted=False, prev_indent=indent)
                self.__modify_list_variants(temp_list, name, dep_list,
                                            add_to_shortname)

            new_list += temp_list

        return new_list


    def parse(self, file, list, restricted=False, prev_indent=-1):
        """
        Read and parse lines from file until a line with an indent level lower
        than or equal to prev_indent is encountered.

        @brief: Parse a file-like object.
        @param file: A file-like object
        @param list: A list of dicts to operate on (list is modified in
        place and should not be used after the call)
        @param restricted: if True, operate in restricted mode
        (prohibit 'variants')
        @param prev_indent: the indent level of the "parent" block
        @return: Return the resulting list of dicts.
        @note: List is destroyed and should not be used after the call.
        Only the returned list should be used.
        """
        while True:
            indent = self.get_next_line_indent(file)
            if indent <= prev_indent:
                break
            indented_line = self.get_next_line(file).rstrip()
            line = indented_line.strip()
            words = line.split()

            len_list = len(list)

            # Look for a known operator in the line
            operators = ["?+=", "?<=", "?=", "+=", "<=", "="]
            op_found = None
            op_pos = len(line)
            for op in operators:
                pos = line.find(op)
                if pos >= 0 and pos < op_pos:
                    op_found = op
                    op_pos = pos

            # Found an operator?
            if op_found:
                if self.debug and not restricted:
                    self.__debug_print(indented_line,
                                       "Parsing operator (%d dicts in current "
                                       "context)" % len_list)
                (left, value) = self.split_and_strip(line, op_found)
                filters_and_key = self.split_and_strip(left, ":")
                filters = filters_and_key[:-1]
                key = filters_and_key[-1]
                filtered_list = list
                for filter in filters:
                    filtered_list = self.filter(filter, filtered_list)
                # Apply the operation to the filtered list
                if op_found == "=":
                    for dict in filtered_list:
                        dict[key] = value
                elif op_found == "+=":
                    for dict in filtered_list:
                        dict[key] = dict.get(key, "") + value
                elif op_found == "<=":
                    for dict in filtered_list:
                        dict[key] = value + dict.get(key, "")
                elif op_found.startswith("?"):
                    exp = re.compile("^(%s)$" % key)
                    if op_found == "?=":
                        for dict in filtered_list:
                            for key in dict.keys():
                                if exp.match(key):
                                    dict[key] = value
                    elif op_found == "?+=":
                        for dict in filtered_list:
                            for key in dict.keys():
                                if exp.match(key):
                                    dict[key] = dict.get(key, "") + value
                    elif op_found == "?<=":
                        for dict in filtered_list:
                            for key in dict.keys():
                                if exp.match(key):
                                    dict[key] = value + dict.get(key, "")

            # Parse 'no' and 'only' statements
            elif words[0] == "no" or words[0] == "only":
                if len(words) <= 1:
                    continue
                filters = words[1:]
                filtered_list = []
                if words[0] == "no":
                    for dict in list:
                        for filter in filters:
                            if self.match(filter, dict):
                                break
                        else:
                            filtered_list.append(dict)
                if words[0] == "only":
                    for dict in list:
                        for filter in filters:
                            if self.match(filter, dict):
                                filtered_list.append(dict)
                                break
                list = filtered_list
                if self.debug and not restricted:
                    self.__debug_print(indented_line,
                                       "Parsing no/only (%d dicts in current "
                                       "context, %d remain)" %
                                       (len_list, len(list)))

            # Parse 'variants'
            elif line == "variants:":
                # 'variants' not allowed in restricted mode
                # (inside an exception or inside subvariants)
                if restricted:
                    e_msg = "Using variants in this context is not allowed"
                    raise error.AutotestError(e_msg)
                if self.debug and not restricted:
                    self.__debug_print(indented_line,
                                       "Entering variants block (%d dicts in "
                                       "current context)" % len_list)
                list = self.parse_variants(file, list, subvariants=False,
                                           prev_indent=indent)

            # Parse 'subvariants' (the block is parsed for each dict
            # separately)
            elif line == "subvariants:":
                if self.debug and not restricted:
                    self.__debug_print(indented_line,
                                       "Entering subvariants block (%d dicts in "
                                       "current context)" % len_list)
                new_list = []
                # Remember current file position
                pos = file.tell()
                # Read the lines in any case
                self.parse_variants(file, [], subvariants=True,
                                    prev_indent=indent)
                # Iterate over the list...
                for index in range(len(list)):
                    # Revert to initial file position in this 'subvariants'
                    # block
                    file.seek(pos)
                    # Everything inside 'subvariants' should be parsed in
                    # restricted mode
                    new_list += self.parse_variants(file, list[index:index+1],
                                                    subvariants=True,
                                                    prev_indent=indent)
                list = new_list

            # Parse 'include' statements
            elif words[0] == "include":
                if len(words) <= 1:
                    continue
                if self.debug and not restricted:
                    self.__debug_print(indented_line,
                                       "Entering file %s" % words[1])
                if self.filename:
                    filename = os.path.join(os.path.dirname(self.filename),
                                            words[1])
                    if os.path.exists(filename):
                        new_file = open(filename, "r")
                        list = self.parse(new_file, list, restricted)
                        new_file.close()
                        if self.debug and not restricted:
                            self.__debug_print("", "Leaving file %s" % words[1])
                    else:
                        logging.warning("Cannot include %s -- file not found",
                                        filename)
                else:
                    logging.warning("Cannot include %s because no file is "
                                    "currently open", words[1])

            # Parse multi-line exceptions
            # (the block is parsed for each dict separately)
            elif line.endswith(":"):
                if self.debug and not restricted:
                    self.__debug_print(indented_line,
                                       "Entering multi-line exception block "
                                       "(%d dicts in current context outside "
                                       "exception)" % len_list)
                line = line.strip(":")
                new_list = []
                # Remember current file position
                pos = file.tell()
                # Read the lines in any case
                self.parse(file, [], restricted=True, prev_indent=indent)
                # Iterate over the list...
                for index in range(len(list)):
                    if self.match(line, list[index]):
                        # Revert to initial file position in this
                        # exception block
                        file.seek(pos)
                        # Everything inside an exception should be parsed in
                        # restricted mode
                        new_list += self.parse(file, list[index:index+1],
                                               restricted=True,
                                               prev_indent=indent)
                    else:
                        new_list += list[index:index+1]
                list = new_list

        return list


    def __debug_print(self, str1, str2=""):
        """
        Nicely print two strings and an arrow.

        @param str1: First string
        @param str2: Second string
        """
        if str2:
            str = "%-50s ---> %s" % (str1, str2)
        else:
            str = str1
        logging.debug(str)


    def __modify_list_variants(self, list, name, dep_list, add_to_shortname):
        """
        Make some modifications to list, as part of parsing a 'variants' block.

        @param list: List to be processed
        @param name: Name to be prepended to the dictionary's 'name' key
        @param dep_list: List of dependencies to be added to the dictionary's
                'depend' key
        @param add_to_shortname: Boolean indicating whether name should be
                prepended to the dictionary's 'shortname' key as well
        """
        for dict in list:
            # Prepend name to the dict's 'name' field
            dict["name"] = self.add_name(dict["name"], name)
            # Prepend name to the dict's 'shortname' field
            if add_to_shortname:
                dict["shortname"] = self.add_name(dict["shortname"], name)
            # Prepend name to each of the dict's dependencies
            for i in range(len(dict["depend"])):
                dict["depend"][i] = self.add_name(dict["depend"][i], name)
            # Add new dependencies
            dict["depend"] += dep_list


    def __modify_list_subvariants(self, list, name, dep_list, add_to_shortname):
        """
        Make some modifications to list, as part of parsing a 'subvariants'
        block.

        @param list: List to be processed
        @param name: Name to be appended to the dictionary's 'name' key
        @param dep_list: List of dependencies to be added to the dictionary's
                'depend' key
        @param add_to_shortname: Boolean indicating whether name should be
                appended to the dictionary's 'shortname' as well
        """
        for dict in list:
            # Add new dependencies
            for dep in dep_list:
                dep_name = self.add_name(dict["name"], dep, append=True)
                dict["depend"].append(dep_name)
            # Append name to the dict's 'name' field
            dict["name"] = self.add_name(dict["name"], name, append=True)
            # Append name to the dict's 'shortname' field
            if add_to_shortname:
                dict["shortname"] = self.add_name(dict["shortname"], name,
                                                  append=True)


if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option('-f', '--file', dest="filename", action='store_true',
                      help='path to a config file that will be parsed. '
                           'If not specified, will parse kvm_tests.cfg '
                           'located inside the kvm test dir.')
    parser.add_option('--verbose', dest="debug", action='store_true',
                      help='include debug messages in console output')

    options, args = parser.parse_args()
    filename = options.filename
    debug = options.debug

    if not filename:
        filename = os.path.join(os.path.dirname(sys.argv[0]), "kvm_tests.cfg")

    # Here we configure the stand alone program to use the autotest
    # logging system.
    logging_manager.configure_logging(KvmLoggingConfig(), verbose=debug)
    list = config(filename, debug=debug).get_list()
    i = 0
    for dict in list:
        logging.info("Dictionary #%d:", i)
        keys = dict.keys()
        keys.sort()
        for key in keys:
            logging.info("    %s = %s", key, dict[key])
        i += 1
