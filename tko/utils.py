import sys, datetime


_debug_logger = sys.stderr
def dprint(msg):
    print >> _debug_logger, msg


def redirect_parser_debugging(ostream):
    global _debug_logger
    _debug_logger = ostream


def get_timestamp(mapping, field):
    val = mapping.get(field, None)
    if val is not None:
        val = datetime.datetime.fromtimestamp(int(val))
    return val
