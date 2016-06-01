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
import logging
import rhsmlib.dbus as common
from rhsmlib.dbus.base_object import BaseObject, BaseProperties, Property

log = logging.getLogger(__name__)


class Config(BaseObject):
    default_dbus_path = common.CONFIG_DBUS_PATH
    interface_name = common.CONFIG_INTERFACE

    def __init__(self, object_path=None, bus_name=None):
        super(Config, self).__init__(conn=None, object_path=object_path, bus_name=bus_name)

    def _create_propertiess(self, interface_name):
        d = {'hello': 'world'}
        properties = BaseProperties.create_instance(interface_name, d, self.PropertiesChanged)
        properties.add('version', Property(value='x', access='write'))

        return properties
