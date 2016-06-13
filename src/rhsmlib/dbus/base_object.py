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
import collections
import dbus.service
import rhsmlib.dbus as common

from rhsmlib.dbus import dbus_utils

log = logging.getLogger(__name__)
common.init_root_logger()


class Property(object):
    default_access = 'read'
    default_value_signature = 's'

    def __init__(self, value, value_signature=None, access=None):
        self.access = access or self.default_access
        self.value = value
        self.value_signature = value_signature or self.default_value_signature


# TODO: Make properties class a gobject, so we can reused it's prop handling
#       (And maybe python-dbus can do something useful with a Gobject?
class BaseProperties(collections.Mapping):
    def __init__(self, interface_name, data=None, properties_changed_callback=None):
        if not data:
            data = {}

        self.props_data = data
        self.interface_name = interface_name
        self.properties_changed_callback = properties_changed_callback

    def __getitem__(self, key):
        self._check_property(key)
        return self.props_data[key]

    def __setitem__(self, key, value):
        if key in self.props_data:
            v = self.props_data[key]

            if v and v.access != 'read':
                self.props_data[key] = dbus_utils.dbus_to_python(value)
        raise common.AccessDenied(key, self.interface_name)

    def __delitem__(self, key):
        del self.props_data[key]

    def __contains__(self, item):
        return item in self.props_data

    def __iter__(self):
        return iter(self.props_data)

    def __len__(self):
        return len(self.props_data)

    @classmethod
    def create_instance(cls, interface_name, prop_dict, properties_changed_callback=None):
        instance = cls(interface_name, properties_changed_callback=properties_changed_callback)
        props = {}
        for key, value in prop_dict.items():
            props[key] = Property(value)

        instance.props_data = props
        return instance

    def get_all(self):
        a = dict([(name, p_v.value) for name, p_v in iter(self)])
        return a

    def add_introspection_xml(self, interface_xml):
        ret = dbus_utils.add_properties(interface_xml, self.interface_name, self.to_introspection_props())
        return ret

    def add(self, name, property):
        """Used to add without hitting __setitem__'s access controls."""
        self.props_data[name] = property

    # FIXME: This only supports string type values at the moment.
    def to_introspection_props(self):
        """ Transform self.props_data (a dict) to:

        data = {'blah': '1', 'blip': some_int_value}
        props_tup = ({'p_t': 's',
                      'p_name': 'blah',
                      'p_access': 'read' },
                      {'p_t': 'i',
                      'p_name': blip,
                      'p_access': 'read'}))
        """
        props_list = []
        props_dict = {}
        for prop_info in self.props_data.values():
            #p_t = dbus_utils._type_map(type(prop_value))
            # FIXME: all strings atm
            props_dict = dict(
                p_t=prop_info.value_signature,
                p_name=prop_info.name,
                p_access=self.access_mask(prop_info.access))
            props_list.append(props_dict)
        return props_list

    def access_mask(self, prop_key):
        return 'read'

    def _check_property(self, property_name):
        if property_name not in self:
            raise common.UnknownProperty(property_name)

    def _emit_properties_changed(self, properties_iterable):
        if not self.properties_changed_callback:
            return

        changed_properties = {}
        invalidated_properties = []

        for property_name, new_value in properties_iterable:
            changed_properties[property_name] = new_value

        self.properties_changed_callback(self.interface_name, changed_properties, invalidated_properties)


class ReadWriteProperties(BaseProperties):
    """A read-write BaseProperties.

    Use this if you want to be able to set()/Set() DBus.Properties
    on a service."""

    def __setitem__(self, key, value):
        if self.access_mask(key) != 'write':
            raise common.AccessDenied(key, self.interface_name)
        self[key] = value

    # FIXME: track read/write per property
    def access_mask(self, prop_key):
        return 'write'


class BaseObject(dbus.service.Object):
    # Name of the DBus interface provided by this object
    interface_name = common.INTERFACE_BASE
    default_dbus_path = common.ROOT_DBUS_PATH

    def __init__(self, conn=None, object_path=None, bus_name=None):
        super(BaseObject, self).__init__(conn=conn, object_path=object_path, bus_name=bus_name)
        self.object_path = self.default_dbus_path

        # TODO: Support multiple interfaces
        self.properties = {self.interface_name: self._create_properties(self.interface_name)}

    def _create_properties(self, interface_name):
        return BaseProperties.create_instance(interface_name, {}, self.PropertiesChanged)

    def _check_interface(self, interface_name):
        if interface_name != self.interface_name:
            raise common.UnknownInterface(interface_name)

    @dbus.service.signal(dbus.PROPERTIES_IFACE, signature='sa{sv}as')
    def PropertiesChanged(self, interface_name, changed_properties, invalidated_properties):
        # TODO: Do something here
        log.debug("Properties Changed emitted.")

    @common.dbus_service_method(
        dbus.PROPERTIES_IFACE,
        in_signature='s',
        out_signature='a{sv}')
    @common.dbus_handle_exceptions
    def GetAll(self, interface_name, sender=None):
        self._check_interface(interface_name)
        return dbus.Dictionary(self.properties[interface_name].get_all(), signature='sv')

    @common.dbus_service_method(
        dbus.PROPERTIES_IFACE,
        in_signature='ss',
        out_signature='v')
    @common.dbus_handle_exceptions
    def Get(self, interface_name, property_name, sender=None):
        self._check_interface(interface_name)
        return self.properties[interface_name][property_name]

    @common.dbus_service_method(
        dbus.PROPERTIES_IFACE,
        in_signature='ssv')
    @common.dbus_handle_exceptions
    def Set(self, interface_name, property_name, new_value, sender=None):
        """Set a DBus property on this object.

        This is the base service class, and defaults to DBus properties
        being read-only. Attempts to Set a property will raise a
        DBusException of type org.freedesktop.DBus.Error.AccessDenied.

        Subclasses that need settable properties should override this."""
        self._check_interface(interface_name)
        self.properties[interface_name][property_name] = new_value
