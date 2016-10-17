# Copyright (c) 2016 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License,
# version 2 (GPLv2). There is NO WARRANTY for this software, express or
# implied, including the implied warranties of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. You should have received a copy of GPLv2
# along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
#
# Red Hat trademarks are not licensed under GPLv2. No permission is
# granted to use or replicate Red Hat trademarks that are incorporated
# in this software or its documentation.
import mock
import dbus
from . import test_config
from rhsmlib.dbus import objects, constants


class ConfigDBusObjectTest(test_config.BaseConfigTest):
    def setUp(self):
        super(ConfigDBusObjectTest, self).setUp()
        self.patcher = mock.patch('rhsmlib.dbus.objects.config.Config')
        self.addCleanup(self.patcher.stop)

        # Hook up a phoney Config object to be returned when Config() is called.
        self.mock_config_clazz = self.patcher.start()
        self.mock_config_clazz.return_value = self.config

    def test_get_all(self):
        config_dbus = objects.ConfigDBusObject()
        result = config_dbus.GetAll(constants.CONFIG_INTERFACE)
        self.assertEqual(self.config['foo']['quux'], result['foo']['quux'])

    def test_get(self):
        config_dbus = objects.ConfigDBusObject()
        result = config_dbus.Get(constants.CONFIG_INTERFACE, 'foo.quux')
        self.assertEqual(self.config['foo']['quux'], result)

    def test_get_section_works(self):
        config_dbus = objects.ConfigDBusObject()
        result = config_dbus.Get(constants.CONFIG_INTERFACE, 'foo')
        self.assertEqual(self.config['foo']['quux'], result['quux'])

    def test_set(self):
        config_dbus = objects.ConfigDBusObject()
        config_dbus.Set(constants.CONFIG_INTERFACE, 'foo.quux', 'new')
        self.assertEqual('new', self.config['foo']['quux'])

    def test_set_section_fails(self):
        config_dbus = objects.ConfigDBusObject()
        with self.assertRaises(dbus.DBusException) as e:
            config_dbus.Set(constants.CONFIG_INTERFACE, 'foo', 'hello')
        self.assertIn('Setting an entire section is not supported', str(e.exception))
