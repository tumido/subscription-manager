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
import dbus
import logging
import rhsmlib.dbus as common

from rhsmlib.dbus.base_object import BaseObject, BaseProperties
from rhsmlib.services.config import Config
from dbus import DBusException

log = logging.getLogger(__name__)


class ConfigDBusObject(BaseObject):
    default_dbus_path = common.CONFIG_DBUS_PATH
    interface_name = common.CONFIG_INTERFACE

    def __init__(self, object_path=None, bus_name=None):
        self.config = Config()
        super(ConfigDBusObject, self).__init__(conn=None, object_path=object_path, bus_name=bus_name)

    def _create_properties(self, interface_name):
        d = {}
        for k, v in self.config.iteritems():
            d[k] = {}
            for kk, vv in v.iteritems():
                d[k][kk] = vv

        properties = BaseProperties.create_instance(interface_name, d, self.PropertiesChanged)
        return properties

    @common.dbus_service_method(
        dbus.PROPERTIES_IFACE,
        in_signature='ssv')
    @common.dbus_handle_exceptions
    def Set(self, interface_name, property_name, new_value, sender=None):
        raise DBusException("Not implemented")
