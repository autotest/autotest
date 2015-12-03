from django.contrib import auth
from south.signals import post_migrate

BASIC_ADMIN = 'Basic admin'


def create_admin_group(app, **kwargs):
    """
    Create a basic admin group with permissions for managing basic autotest
    objects.
    """
    print "Creatin/updating Basic admin group"
    admin_group, created = auth.models.Group.objects.get_or_create(
        name=BASIC_ADMIN)
    admin_group.save()  # must save before adding permissions
    PermissionModel = auth.models.Permission
    have_permissions = list(admin_group.permissions.all())
    for model_name in ('host', 'label', 'test', 'aclgroup', 'profiler',
                       'atomicgroup'):
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

post_migrate.connect(create_admin_group)
