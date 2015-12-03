"""
Module for testing config file changes.

:author: Kristof Katus and Plamen Dimitrov
:copyright: Intra2net AG 2012
@license: GPL v2
"""

import commands
import os
import shutil


def get_temp_file_path(file_path):
    """
    Generates a temporary filename
    """
    return file_path + '.tmp'


def make_temp_file_copies(file_paths):
    """
    Creates temporary copies of the provided files
    """
    for file_path in file_paths:
        temp_file_path = get_temp_file_path(file_path)
        shutil.copyfile(file_path, temp_file_path)


def del_temp_file_copies(file_paths):
    """
    Deletes all the provided files
    """
    for file_path in file_paths:
        temp_file_path = get_temp_file_path(file_path)
        os.remove(temp_file_path)


def parse_unified_diff_output(lines):
    """
    Parses the unified diff output of two files

    Returns a pair of adds and removes, where each is a list of trimmed lines
    """
    adds = []
    removes = []
    for line in lines:
        # ignore filepaths in the output
        if (len(line) > 2 and
            (line[:3] == "+++" or
                line[:3] == "---")):
            continue
        # ignore line range information in the output
        elif len(line) > 1 and line[:2] == "@@":
            continue
        # gather adds
        elif len(line) > 0 and line[0] == "+":
            added_line = line[1:].lstrip().rstrip()
            if len(added_line) == 0:
                continue
            adds = adds + [added_line]
        # gather removes
        elif len(line) > 0 and line[0] == "-":
            removed_line = line[1:].lstrip().rstrip()
            if len(removed_line) == 0:
                continue
            removes = removes + [removed_line]
    return (adds, removes)


def extract_config_changes(file_paths, compared_file_paths=[]):
    """
    Extracts diff information based on the new and
    temporarily saved old config files

    Returns a dictionary of file path and corresponding
    diff information key-value pairs.
    """
    changes = {}

    for i in range(len(file_paths)):
        temp_file_path = get_temp_file_path(file_paths[i])

        if len(compared_file_paths) > i:
            command = ("diff -U 0 -b " + compared_file_paths[i] + " " +
                       file_paths[i])
        else:
            command = "diff -U 0 -b " + temp_file_path + " " + file_paths[i]

        (_, output) = commands.getstatusoutput(command)
        lines = output.split('\n')
        changes[file_paths[i]] = parse_unified_diff_output(lines)
    return changes


def assert_config_change_dict(actual_result, expected_result):
    """
    Calculates unexpected line changes.

    The arguments actual_result and expected_results are of
    the same data structure type: Dict[file_path] --> (adds, removes),
    where adds = [added_line, ...] and removes = [removed_line, ...].

    The return value has the following structure:
    Dict[file_path] --> (unexpected_adds,
                         not_present_adds,
                         unexpected_removes,
                         not_present_removes)
    """
    change_diffs = {}
    for file_path, actual_changes in actual_result.items():
        expected_changes = expected_result[file_path]

        actual_adds = actual_changes[0]
        actual_removes = actual_changes[1]
        expected_adds = expected_changes[0]
        expected_removes = expected_changes[1]

        # Additional unexpected adds -- they should have been not added
        unexpected_adds = sorted(set(actual_adds) - set(expected_adds))
        # Not present expected adds -- they should have been added
        not_present_adds = sorted(set(expected_adds) - set(actual_adds))
        # Additional unexpected removes - they should have been not removed
        unexpected_removes = sorted(set(actual_removes) - set(expected_removes))
        # Not present expected removes - they should have been removed
        not_present_removes = sorted(set(expected_removes) -
                                     set(actual_removes))

        change_diffs[file_path] = (unexpected_adds, not_present_adds,
                                   unexpected_removes, not_present_removes)

    return change_diffs


def assert_config_change(actual_result, expected_result):
    """
    Wrapper of the upper method returning boolean true if no config changes
    were detected.
    """
    change_diffs = assert_config_change_dict(actual_result, expected_result)
    for file_change in change_diffs.values():
        for line_change in file_change:
            if len(line_change) != 0:
                return False
    return True


def print_change_diffs(change_diffs):
    """
    Pretty prints the output of the evaluate_config_changes function
    """
    diff_strings = []
    for file_path, change_diff in change_diffs.items():
        if not (change_diff[0] or change_diff[1] or
                change_diff[2] or change_diff[3]):
            continue
        diff_strings.append("--- %s" % get_temp_file_path(file_path))
        diff_strings.append("+++ %s" % file_path)
        for iter_category in range(4):
            change_category = change_diff[iter_category]
            if iter_category == 0 and change_category:
                diff_strings.append("*++ Additional unexpected adds")
            elif iter_category == 1 and change_category:
                diff_strings.append("/++ Not present expected adds")
            elif iter_category == 2 and change_category:
                diff_strings.append("*-- Additional unexpected removes")
            elif iter_category == 3 and change_category:
                diff_strings.append("/-- Not present expected removes")
            for line_change in change_category:
                diff_strings.append(str(line_change).encode("string-escape"))
    return "\n".join(diff_strings)
