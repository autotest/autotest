"""
Convenience functions for use by tests or whomever.

NOTE: this is a mixin library that pulls in functions from several places
Note carefully what the precendece order is

There's no really good way to do this, as this isn't a class we can do
inheritance with, just a collection of static methods.
"""

from autotest.client.shared.utils import *
from autotest.server.base_utils import *
if os.path.exists(os.path.join(os.path.dirname(__file__), 'site_utils.py')):
    # Here we are importing site utils only if it exists
    # pylint: disable=E0611
    from autotest.server.site_utils import *
