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
import unittest

from tempfile import NamedTemporaryFile
from rhsmlib.services.config import Config, ConfigSection
from rhsm.config import RhsmConfigParser

TEST_CONFIG = """
[foo]
bar =
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
"""


class BaseConfigTest(unittest.TestCase):
    expected_sections = ['foo', 'server', 'rhsm', 'rhsmcertd']

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

    def test_no_overwrite_sections(self):
        self.parser.add_section("new_section")

        with self.assertRaises(NotImplementedError):
            self.config['server'] = {}

    def test_get_item(self):
        self.assertIsInstance(self.config['server'], ConfigSection)


class TestConfigSection(BaseConfigTest):
    def test_get_value(self):
        self.assertEquals('1', self.config['server']['insecure'])

    def test_get_missing_value(self):
        with self.assertRaises(KeyError):
            self.config['server']['missing']
