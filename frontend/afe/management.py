# use some undocumented Django tricks to execute custom logic after syncdb

from django.dispatch import dispatcher
from django.db.models import signals
from django.contrib import auth
import common
from autotest_lib.frontend.afe import models

BASIC_ADMIN = 'Basic admin'

def create_admin_group(app, created_models, verbosity, **kwargs):
    """\
    Create a basic admin group with permissions for managing basic autotest
    objects.
    """
    admin_group, created = auth.models.Group.objects.get_or_create(
        name=BASIC_ADMIN)
    admin_group.save() # must save before adding permissions
    PermissionModel = auth.models.Permission
    have_permissions = list(admin_group.permissions.all())
    for model_name in ('host', 'label', 'test', 'acl_group', 'profiler'):
        for permission_type in ('add', 'change', 'delete'):
            codename = permission_type + '_' + model_name
            permissions = list(PermissionModel.objects.filter(
                codename=codename))
            if len(permissions) == 0:
                print '  No permission ' + codename
                continue
            for permission in permissions:
                if permission not in have_permissions:
                    print '  Adding permission ' + codename
                    admin_group.permissions.add(permission)
    if created:
        print 'Created group "%s"' % BASIC_ADMIN
    else:
        print 'Group "%s" already exists' % BASIC_ADMIN


dispatcher.connect(create_admin_group, sender=models,
                   signal=signals.post_syncdb)
