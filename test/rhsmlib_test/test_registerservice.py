#
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
import mock
import json
import dbus.connection

import rhsm.connection

from ..fixture import SubManFixture
from rhsmlib.dbus import dbus_utils
from rhsmlib.dbus.objects import RegisterService


class TestRegisterService(SubManFixture):
    def setUp(self):
        self.dbus_connection = mock.Mock(spec=dbus.connection.Connection)
        super(TestRegisterService, self).setUp()

    @mock.patch("subscription_manager.managerlib.persist_consumer_cert")
    @mock.patch("rhsm.connection.UEPConnection")
    def test_register(self, stub_uep, mock_persist_consumer):
        successful_registration = {
            "headers": {'content-type': 'application/json',
                'date': 'Thu, 02 Jun 2016 15:16:51 GMT',
                'server': 'Apache-Coyote/1.1',
                'transfer-encoding': 'chunked',
                'x-candlepin-request-uuid': '01566658-137b-478c-84c0-38540daa8602',
                'x-version': '2.0.13-1'},
            "content": '{"hypervisorId": null,'
                '"serviceLevel": "",'
                '"autoheal": true,'
                '"idCert": "FAKE_KEY",'
                '"owner": {"href": "/owners/admin", "displayName": "Admin Owner",'
                '"id": "ff808081550d997c01550d9adaf40003", "key": "admin"},'
                '"href": "/consumers/c1b8648c-6f0a-4aa5-b34e-b9e62c0e4364",'
                '"facts": {}, "id": "ff808081550d997c015511b0406d1065",'
                '"uuid": "c1b8648c-6f0a-4aa5-b34e-b9e62c0e4364",'
                '"guestIds": null, "capabilities": null,'
                '"environment": null, "installedProducts": null,'
                '"canActivate": false, "type": {"manifest": false,'
                '"id": "1000", "label": "system"}, "annotations": null,'
                '"username": "admin", "updated": "2016-06-02T15:16:51+0000",'
                '"lastCheckin": null, "entitlementCount": 0, "releaseVer":'
                '{"releaseVer": null}, "entitlementStatus": "valid", "name":'
                '"test.example.com", "created": "2016-06-02T15:16:51+0000",'
                '"contentTags": null, "dev": false}',
            "status": "200"
        }

        self._inject_mock_invalid_consumer()

        expected_consumer = json.loads(successful_registration['content'],
            object_hook=dbus_utils._decode_dict)
        del expected_consumer['idCert']
        stub_uep.return_value.registerConsumer = mock.Mock(
                return_value=successful_registration)
        register_service = RegisterService(self.dbus_connection)
        username = password = org = 'admin'
        options = {
            'host': 'localhost',
            'port': '8443',
            'handler': '/candlepin'
        }
        output = register_service.register(username, password, org, options)

        # Be sure we are persisting the consumer cert
        mock_persist_consumer.assert_called_once_with(expected_consumer)
        # Be sure we get the right output
        self.assertEquals(output, successful_registration)

    @mock.patch("rhsm.connection.UEPConnection")
    def test_get_uep_from_options(self, stub_uep):
        stub_uep.return_value = mock.Mock(spec=rhsm.connection.UEPConnection)
        options = {
            'username': 'test',
            'password': 'test_password',
            'host': 'localhost',
            'port': '8443',
            'handler': '/candlepin',
            'insecure': True
        }

        self._inject_mock_invalid_consumer()

        RegisterService._get_uep_from_options(options)

        stub_uep.assert_called_once_with(
            username=options.get('username', None),
            password=options.get('password', None),
            host=options.get('host', None),
            ssl_port=rhsm.connection.safe_int(options.get('port', None)),
            handler=options.get('handler', None),
            insecure=options.get('insecure', None),
            proxy_hostname=options.get('proxy_hostname', None),
            proxy_port=options.get('proxy_port', None),
            proxy_user=options.get('proxy_user', None),
            proxy_password=options.get('proxy_password', None),
            restlib_class=rhsm.connection.BaseRestLib
        )

    @mock.patch("subscription_manager.managerlib.persist_consumer_cert")
    @mock.patch("rhsm.connection.UEPConnection")
    def test_register_with_activation_keys(self, stub_uep, mock_persist_consumer):
        successful_registration = {
            "headers": {'content-type': 'application/json',
                'date': 'Thu, 02 Jun 2016 15:16:51 GMT',
                'server': 'Apache-Coyote/1.1',
                'transfer-encoding': 'chunked',
                'x-candlepin-request-uuid': '01566658-137b-478c-84c0-38540daa8602',
                'x-version': '2.0.13-1'},
            "content": '{"hypervisorId": null,'
                '"serviceLevel": "",'
                '"autoheal": true,'
                '"idCert": "FAKE_KEY",'
                '"owner": {"href": "/owners/admin", "displayName": "Admin Owner",'
                '"id": "ff808081550d997c01550d9adaf40003", "key": "admin"},'
                '"href": "/consumers/c1b8648c-6f0a-4aa5-b34e-b9e62c0e4364",'
                '"facts": {}, "id": "ff808081550d997c015511b0406d1065",'
                '"uuid": "c1b8648c-6f0a-4aa5-b34e-b9e62c0e4364",'
                '"guestIds": null, "capabilities": null,'
                '"environment": null, "installedProducts": null,'
                '"canActivate": false, "type": {"manifest": false,'
                '"id": "1000", "label": "system"}, "annotations": null,'
                '"username": "admin", "updated": "2016-06-02T15:16:51+0000",'
                '"lastCheckin": null, "entitlementCount": 0, "releaseVer":'
                '{"releaseVer": null}, "entitlementStatus": "valid", "name":'
                '"test.example.com", "created": "2016-06-02T15:16:51+0000",'
                '"contentTags": null, "dev": false}',
            "status": "200"
        }

        self._inject_mock_invalid_consumer()

        expected_consumer = json.loads(successful_registration['content'],
            object_hook=dbus_utils._decode_dict)
        del expected_consumer['idCert']
        stub_uep.return_value.registerConsumer = mock.Mock(
                return_value=successful_registration)
        register_service = RegisterService(self.dbus_connection)
        org = 'admin'
        keys = ['default_key']
        options = {
            'host': 'localhost',
            'port': '8443',
            'handler': '/candlepin'
        }
        output = register_service.register_with_activation_keys(
            org,
            keys,
            options
        )

        # Be sure we are persisting the consumer cert
        mock_persist_consumer.assert_called_once_with(expected_consumer)
        # Be sure we get the right output
        self.assertEquals(output, successful_registration)
