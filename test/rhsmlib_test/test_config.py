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
#
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import dbus

from tempfile import NamedTemporaryFile
from rhsmlib.services.config import Config, ConfigSection
from rhsm.config import RhsmConfigParser, NoOptionError
from rhsmlib.dbus.objects.config import ConfigDBusObject

from test.rhsmlib_test.base import DBusObjectTest, import_class

TEST_CONFIG = """
[foo]
bar =
quux = baz
bigger_than_32_bit = 21474836470
bigger_than_64_bit = 123456789009876543211234567890

[server]
hostname = server.example.conf
prefix = /candlepin
port = 8443
insecure = 1
ssl_verify_depth = 3
proxy_hostname =
proxy_port =
proxy_user =
proxy_password =

[rhsm]
ca_cert_dir = /etc/rhsm/ca-test/
baseurl= https://content.example.com
repo_ca_cert = %(ca_cert_dir)sredhat-uep-non-default.pem
productCertDir = /etc/pki/product
entitlementCertDir = /etc/pki/entitlement
consumerCertDir = /etc/pki/consumer
report_package_profile = 1
pluginDir = /usr/lib/rhsm-plugins
some_option = %(repo_ca_cert)stest
manage_repos =

[rhsmcertd]
certCheckInterval = 245

[logging]
default_log_level = DEBUG
"""


class BaseConfigTest(unittest.TestCase):
    expected_sections = ['foo', 'server', 'rhsm', 'rhsmcertd', 'logging']

    def write_temp_file(self, data):
        # create a temp file for use as a config file. This should get cleaned
        # up magically at the end of the run.
        fid = NamedTemporaryFile(mode='w+b', suffix='.tmp')
        fid.write(data)
        fid.seek(0)
        return fid

    def setUp(self):
        self.fid = self.write_temp_file(TEST_CONFIG)
        self.parser = RhsmConfigParser(self.fid.name)
        self.config = Config(self.parser)

    def assert_items_equals(self, a, b):
        """Assert that two lists contain the same items regardless of order."""
        if sorted(a) != sorted(b):
            self.fail("%s != %s" % (a, b))
        return True


class TestConfig(BaseConfigTest):
    def test_config_contains(self):
        self.assertTrue('server' in self.config)
        self.assertFalse('not_here' in self.config)

    def test_config_len(self):
        self.assertEquals(len(self.expected_sections), len(self.config))

    def test_keys(self):
        self.assert_items_equals(self.expected_sections, self.config.keys())

    def test_values(self):
        values = self.config.values()
        for v in values:
            self.assertIsInstance(v, ConfigSection)

    def test_set_new_section(self):
        self.config['new_section'] = {'hello': 'world'}
        self.assertEquals(['hello'], self.config._parser.options('new_section'))
        self.assertEquals('world', self.config._parser.get('new_section', 'hello'))

    def test_set_old_section(self):
        self.config['foo'] = {'hello': 'world'}
        self.assertEquals(['hello'], self.config._parser.options('foo'))
        self.assertEquals('world', self.config._parser.get('foo', 'hello'))
        self.assertRaises(NoOptionError, self.config._parser.get, 'foo', 'quux')

    def test_get_item(self):
        self.assertIsInstance(self.config['server'], ConfigSection)

    def test_persist(self):
        self.config['foo'] = {'hello': 'world'}
        self.config.persist()
        reparsed = RhsmConfigParser(self.fid.name)
        self.assertEquals('world', reparsed.get('foo', 'hello'))
        self.assertRaises(NoOptionError, reparsed.get, 'foo', 'quux')

    def test_auto_persists(self):
        config = Config(self.parser, auto_persist=True)
        config['foo'] = {'hello': 'world'}
        reparsed = RhsmConfigParser(self.fid.name)
        self.assertEquals('world', reparsed.get('foo', 'hello'))
        self.assertRaises(NoOptionError, reparsed.get, 'foo', 'quux')

    def test_does_not_auto_persist_by_default(self):
        config = Config(self.parser, auto_persist=False)
        config['foo'] = {'hello': 'world'}
        reparsed = RhsmConfigParser(self.fid.name)
        self.assertEquals('baz', reparsed.get('foo', 'quux'))
        self.assertRaises(NoOptionError, reparsed.get, 'foo', 'hello')

    def test_del_item(self):
        del self.config['foo']
        self.assertFalse(self.config._parser.has_section('foo'))

    def test_iter(self):
        sections = [s for s in self.config]
        self.assert_items_equals(self.expected_sections, sections)


class TestConfigSection(BaseConfigTest):
    def test_get_value(self):
        self.assertEquals('1', self.config['server']['insecure'])

    def test_get_missing_value(self):
        with self.assertRaises(KeyError):
            self.config['server']['missing']

    def test_set_item(self):
        self.assertEquals('baz', self.config['foo']['quux'])
        self.config['foo']['quux'] = 'fizz'
        self.assertEquals('fizz', self.config['foo']['quux'])

    def test_auto_persist(self):
        config = Config(self.parser, auto_persist=True)
        self.assertEquals('baz', config['foo']['quux'])
        config['foo']['quux'] = 'fizz'
        self.assertEquals('fizz', config['foo']['quux'])

        reparsed = RhsmConfigParser(self.fid.name)
        self.assertEquals('fizz', reparsed.get('foo', 'quux'))

    def test_persist_cascades(self):
        config = Config(self.parser, auto_persist=False)
        self.assertEquals('baz', config['foo']['quux'])
        config['foo']['quux'] = 'fizz'
        config.persist()
        self.assertEquals('fizz', config['foo']['quux'])

        reparsed = RhsmConfigParser(self.fid.name)
        self.assertEquals('fizz', reparsed.get('foo', 'quux'))

    def test_del_item(self):
        del self.config['foo']['quux']
        self.assertNotIn('quux', self.config['foo'])

        with self.assertRaises(KeyError):
            del self.config['foo']['missing_key']

    def test_len(self):
        self.assertEquals(4, len(self.config['foo']))

    def test_in(self):
        self.assertIn("quux", self.config['foo'])
        self.assertNotIn("missing", self.config['foo'])


class TestConfigDBusObject(DBusObjectTest):
    def postServerSetUp(self):
        self.bus = import_class(self.bus_class_name)()
        self.proxy = self.bus.get_object(
            self.bus_name, ConfigDBusObject.default_dbus_path)
        self.interface = dbus.Interface(self.proxy, dbus_interface=dbus.PROPERTIES_IFACE)

    def dbus_objects(self):
        return [ConfigDBusObject]

    def test_get_all(self):
        config = self.interface.GetAll(ConfigDBusObject.interface_name)
        self.assertIn("server", config)

    def test_get_property(self):
        self.interface.Get(ConfigDBusObject.interface_name, 'server.hostname')

    def test_get_section(self):
        config = self.interface.Get(ConfigDBusObject.interface_name, 'server')
        self.assertIn('hostname', config)
