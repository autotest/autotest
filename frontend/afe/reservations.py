#!/usr/bin/python

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

__author__ = """Julius Gawlas <julius.gawlas@hp.com> """

'''
Implementaion note:
Reservations are implemented using acl mechanism to minimize
changes to the core;
If we reserve a system for a user acl is created
with the same name as username and host is placed in that acl,
release simple removes the system from that acl
'''
from autotest.frontend.afe import models


def create(hosts_to_reserve, username=None):
    """\
    Reserve hosts for user, throws AclAccessViolation if
    user cannot reserve all specified hosts
    @param hosts_to_reserve list of strings or idents for hosts to reserve
    @param username string, login of the user reserving hosts
    """
    hosts = models.Host.smart_get_bulk(hosts_to_reserve)
    if not hosts:
        raise Exception("At least one host must be specified")
    if username:
        user = models.User.objects.get(login=username)
    else:
        user = models.User.current_user()
    # check if this user can access specified hosts
    models.AclGroup.check_for_acl_violation_hosts(hosts, user.login)
    user_acl, created = models.AclGroup.objects.get_or_create(name=user.login)
    if created:
        user_acl.users = [user]
        user_acl.save()
    for host in hosts:
        # remove host from other acls
        user_acl.hosts.clear()
        host.aclgroup_set.add(user_acl)
        # and add to reservation acl
        user_acl.hosts.add(*hosts)
        user_acl.on_host_membership_change()


def release(hosts_to_release, username=None):
    """\
    Release a collection of hosts from user, its ok if user
    does not own these systems (nop)
    @param hosts_to_release list of strings or idents for hosts to release
    @param username string, login of the user reserving hosts
    """
    hosts = models.Host.smart_get_bulk(hosts_to_release)
    if not hosts:
        raise Exception("At least one host must be specified")
    if username:
        user = models.User.objects.get(login=username)
    else:
        user = models.User.current_user()
    acls = models.AclGroup.objects.filter(name=user.login)
    if acls:
        user_acl = acls[0]
        user_acl.hosts.remove(*hosts)
        user_acl.on_host_membership_change()
