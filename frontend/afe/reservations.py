#
# Copyright 2013 Hewlett-Packard Development Company, L.P.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of version 2 of the GNU General Public License
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to:
#   Free Software Foundation, Inc.
#   51 Franklin Street, Fifth Floor
#   Boston, MA 02110-1301, USA.
#


__author__ = "Julius Gawlas <julius.gawlas@hp.com>"

from autotest.frontend.afe import models


__all__ = ['create', 'release', 'force_release']


#
# Implementation notes:
#
# Reservations are implemented using ACL mechanism to minimize changes to the
# core. If we reserve a system for a user ACL is created with the same name as
# username and host is placed in that ACL, release simple removes the system
# from that ACL
#


def get_user(username=None):
    '''
    Get the specificed user object or the current user if none is specified

    :param username: login of the user reserving hosts
    :type username: str
    :returns: the user object for the given username
    :rtype: :class:`models.User`
    '''
    if username:
        user = models.User.objects.get(login=username)
    else:
        user = models.User.current_user()
    return user


def create(hosts_to_reserve, username=None):
    """
    Reserve hosts for user

    :param hosts_to_reserve: strings or idents for hosts to reserve
    :type hosts_to_reserve: list
    :param username: login of the user reserving hosts
    :type username: str
    :raises: AclAccessViolation if user cannot reserve all specified hosts
    """
    hosts = models.Host.smart_get_bulk(hosts_to_reserve)
    if not hosts:
        raise Exception("At least one host must be specified")
    # check if this user can access specified hosts
    user = get_user(username)
    models.AclGroup.check_for_acl_violation_hosts(hosts, user.login)
    user_acl, created = models.AclGroup.objects.get_or_create(name=user.login)
    if created:
        user_acl.users = [user]
        user_acl.save()
    for host in hosts:
        host.aclgroup_set.add(user_acl)
        # and add to reservation acl
        user_acl.hosts.add(*hosts)
        user_acl.on_host_membership_change()


def release(hosts_to_release, username=None):
    """
    Release a collection of hosts from user

    It's OK if user does not own these systems, in which case this does nothing

    :param hosts_to_release: strings or idents for hosts to release
    :type hosts_to_release: list
    :param username: login of the user reserving hosts
    :type username: str
    """
    hosts = models.Host.smart_get_bulk(hosts_to_release)
    if not hosts:
        raise Exception("At least one host must be specified")
    user = get_user(username)
    acls = models.AclGroup.objects.filter(name=user.login)
    if acls:
        user_acl = acls[0]
        user_acl.hosts.remove(*hosts)
        user_acl.on_host_membership_change()


def force_release(hosts_to_release, username=None):
    """
    Force release a collection of hosts from user

    This will remove all ACLs from the hosts

    :param hosts_to_release: strings or idents for hosts to release
    :type hosts_to_release: list
    :param username: login of the user reserving hosts
    :type username: str
    """
    hosts = models.Host.smart_get_bulk(hosts_to_release)
    if not hosts:
        raise Exception("At least one host must be specified")
    user = get_user(username)
    if not user.is_superuser():
        raise Exception("Must be super user to force release")
    acls = models.AclGroup.objects.all()
    for user_acl in acls:
        user_acl.hosts.remove(*hosts)
        user_acl.on_host_membership_change()
