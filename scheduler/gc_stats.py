# Compute and gather statistics about garbage collection in this process.
# This module depends on the CPython gc module and garbage collection behavior.

import gc, logging, pprint


verbose = False


# A mapping from type objects to a count of instances of those types in the
# garbage collectors all objects list on the previous call to
# _log_garbage_collector_stats().
_previous_obj_type_map = {}


# A set of object ids for everything in the all objects list on the
# previous call to _log_garbage_collector_stats().
_previous_obj_ids = set()


def _log_garbage_collector_stats(minimum_count=10):
    """
    Log statistics about how many of what type of Python object exist in this
    process.

    @param minimum_count: The minimum number of instances of a type for it
            to be considered worthy of logging.
    """
    global _previous_obj_type_map
    global _previous_obj_ids

    # We get all objects -before- creating any new objects within this function.
    # to avoid having our own local instances in the list.
    all_objects = gc.get_objects()
    obj = None
    new_objects = []
    try:
        obj_type_map = {}
        object_ids = set()
        for obj in all_objects:
            obj_type = type(obj)
            obj_type_map.setdefault(obj_type, 0)
            obj_type_map[obj_type] += 1
            object_ids.add(id(obj))
        whats_new_big_str = ''
        if verbose and _previous_obj_ids:
            new_object_ids = object_ids - _previous_obj_ids
            for obj in all_objects:
                if id(obj) in new_object_ids:
                    new_objects.append(obj)
            whats_new_big_str = pprint.pformat(new_objects, indent=1)
    finally:
        # Never keep references to stuff returned by gc.get_objects() around
        # or it'll just make the future cyclic gc runs more difficult.
        del all_objects
        del obj
        del new_objects


    delta = {}
    for obj_type, count in obj_type_map.iteritems():
        if obj_type not in _previous_obj_type_map:
            delta[obj_type] = count
        elif _previous_obj_type_map[obj_type] != count:
            delta[obj_type] = count - _previous_obj_type_map[obj_type]

    sorted_stats = reversed(sorted(
            (count, obj_type) for obj_type, count in obj_type_map.iteritems()))
    sorted_delta = reversed(sorted(
            (count, obj_type) for obj_type, count in delta.iteritems()))

    logging.debug('Garbage collector object type counts:')
    for count, obj_type in sorted_stats:
        if count >= minimum_count:
            logging.debug('  %d\t%s', count, obj_type)

    logging.info('Change in object counts since previous GC stats:')
    for change, obj_type in sorted_delta:
        if obj_type_map[obj_type] > minimum_count:
            logging.info('  %+d\t%s\tto %d', change, obj_type,
                         obj_type_map[obj_type])

    if verbose and whats_new_big_str:
        logging.debug('Pretty printed representation of the new objects:')
        logging.debug(whats_new_big_str)

    _previous_obj_type_map = obj_type_map
    if verbose:
        _previous_obj_ids = object_ids
