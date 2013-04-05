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


import unittest

try:
    import autotest.common as common
except ImportError:
    import common
from autotest.frontend import setup_django_environment
from autotest.frontend.afe import frontend_test_utils
from autotest.frontend.afe import models, reservations
from autotest.frontend import thread_local


class ReservationsTest(unittest.TestCase,
                   frontend_test_utils.FrontendTestMixin):
    def setUp(self):
        self._frontend_common_setup()
        self._create_basic_reservation_data()

    def tearDown(self):
        self._frontend_common_teardown()

    def _create_basic_reservation_data(self):
        self.reservation_hosts = [models.Host.objects.create(hostname=hostname)
                      for hostname in
                      ('reshost1', 'reshost2', 'reshost3', 'reshost4')]
        self.user1 = models.User.objects.create(login='resuser1')
        self.user2 = models.User.objects.create(login='resuser2')
        reservations.create(['reshost4'], self.user2.login)

    def test_unreservable_already_reserved(self):
        #explicitly reserved
        self.assertRaises(models.AclAccessViolation,
                          reservations.create,
                          ['reshost4'],
                          self.user1.login)

    def test_unreservable_in_another_acl(self):
        #in another acl
        models.AclGroup.check_for_acl_violation_hosts(
                        self.reservation_hosts[2:3],
                        self.user2.login)

    def test_normal_reserve_lifecycle(self):
        #reserve few hosts
        host_names = [h.hostname for h in self.reservation_hosts[0:2]]
        reservations.create(host_names, self.user1.login)
        #second user cannot access it
        self.assertRaises(models.AclAccessViolation,
                          models.AclGroup.check_for_acl_violation_hosts,
                          self.reservation_hosts[0:2],
                          self.user2.login)
        reservations.release(host_names, self.user1.login)
        models.AclGroup.check_for_acl_violation_hosts(self.reservation_hosts[0:2], self.user2.login)

    def test_nop_release(self):
        #release from wrong user, nop
        reservations.release(['reshost4'], self.user1.login)
        #still cannot access
        self.assertRaises(models.AclAccessViolation,
                          reservations.create,
                          ['reshost4'],
                          self.user1.login)

    def test_reservations_default_user(self):
        #test if we handle default logged in user
        thread_local.set_user(self.user1)
        self.assertRaises(models.AclAccessViolation,
                          reservations.create,
                          ['reshost4'])

    def test_reservations_no_hosts(self):
        #test if we handle default logged in user
        self.assertRaises(Exception,
                          reservations.create,
                          ['blah', 'woof'])


if __name__ == '__main__':
    unittest.main()
