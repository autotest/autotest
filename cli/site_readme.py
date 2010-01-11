#
# Copyright 2008 Google Inc. All Rights Reserved.

"""
If you need to change the default behavior of some atest commands, you
can create a site_<topic>.py file to subclass some of the classes from
<topic>.py.

The following example would prevent the creation of platform labels.
"""

import inspect, new, sys

from autotest_lib.cli import topic_common, label


class site_label(label.label):
    pass


class site_label_create(label.label_create):
    """Disable the platform option
    atest label create <labels>|--blist <file>"""
    def __init__(self):
        super(site_label_create, self).__init__()
        self.parser.remove_option("--platform")


    def parse(self):
        (options, leftover) = super(site_label_create, self).parse()
        self.is_platform = False
        return (options, leftover)


# The following boiler plate code should be added at the end to create
# all the other site_<topic>_<action> classes that do not modify their
# <topic>_<action> super class.

# Any classes we don't override in label should be copied automatically
for cls in [getattr(label, n) for n in dir(label) if not n.startswith("_")]:
    if not inspect.isclass(cls):
        continue
    cls_name = cls.__name__
    site_cls_name = 'site_' + cls_name
    if hasattr(sys.modules[__name__], site_cls_name):
        continue
    bases = (site_label, cls)
    members = {'__doc__': cls.__doc__}
    site_cls = new.classobj(site_cls_name, bases, members)
    setattr(sys.modules[__name__], site_cls_name, site_cls)
