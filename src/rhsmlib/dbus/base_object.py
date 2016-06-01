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
import dbus.service
import rhsmlib.dbus as common

from rhsmlib.dbus import dbus_utils

log = logging.getLogger(__name__)
common.init_root_logger()


class Property(object):
    default_access = 'read'
    default_value_signature = 's'

    def __init__(self, name, value, value_signature=None, access=None):
        self.access = access or self.default_access
        self.name = name
        self.value = value
        self.value_signature = value_signature or self.default_value_signature


# TODO: Make properties class a gobject, so we can reused it's prop handling
#       (And maybe python-dbus can do something useful with a Gobject?
class BaseProperties(object):
    def __init__(self, interface_name, data=None, properties_changed_callback=None):
        self.props_data = data  # dict of prop_name: property_object
        self.interface_name = interface_name
        self.properties_changed_callback = properties_changed_callback

    @classmethod
    def create_instance(cls, interface_name, prop_dict, properties_changed_callback=None):
        base_prop = cls(interface_name, properties_changed_callback=properties_changed_callback)
        props = {}
        for prop_key, prop_value in prop_dict.items():
            prop = Property(name=prop_key, value=prop_value)
            props[prop.name] = prop

        base_prop.props_data = props
        return base_prop

    def get(self, interface_name=None, property_name=None):
        self._check_interface(interface_name)
        self._check_prop(property_name)

        try:
            return self.props_data[property_name].value
        except KeyError as e:
            self.log.exception(e)
            self.raise_access_denied_or_unknown_property(property_name)

    def get_all(self, interface_name=None):
        if interface_name != self.interface_name:
            raise common.UnknownInterface(interface_name)

        a = dict([(p_name, p_v.value) for p_name, p_v in self.props_data.items()])
        return a

    def set(self, interface_name, property_name, new_value):
        """On attempts to set a property, raise AccessDenied.

        The default base_properties is read-only. Attempts to set()
        a property will raise a DBusException of type
        org.freedesktop.DBus.Error.AccessDenied.

        Subclasses that need settable properties should override this.
        BaseService subclasses that need rw properties should use
        a ReadWriteBaseProperties instead of BaseProperties."""
        self.raise_access_denied(property_name)

    def _set(self, interface_name, property_name, new_value):
        """Set a property to given value, ignoring access writes.

        Ie, BaseProperties.set() can be exposed through the dbus.Properties 'Set()'
        method, where it will check access rights. But internal use can use _set."""
        self._set_prop(interface_name, property_name, new_value)

    def _set_props(self, interface_name, properties_iterable):
        for property_name, new_value in properties_iterable:
            self._set_prop(interface_name, property_name, new_value)
        self._emit_properties_changed(properties_iterable)

    def _set_prop(self, interface_name, property_name, new_value):
        interface_name = dbus_utils.dbus_to_python(interface_name, str)
        if interface_name != self.interface_name:
            raise common.UnknownInterface(interface_name)

        property_name = dbus_utils.dbus_to_python(property_name, str)
        new_value = dbus_utils.dbus_to_python(new_value)

        self._check_prop(property_name)

        # FIXME/TODO: Plug in access checks and data validation
        # FIXME/TODO: Plug in checking if prop should emit a change signal.
        try:
            self.props_data[property_name].value = new_value
        except Exception as e:
            msg = "Error setting property %s=%s on interface_name=%s: %s" % \
                (property_name, new_value, self.interface_name)
            self.log.exception(e)
            raise common.Failed(msg)

    def add_introspection_xml(self, interface_xml):
        ret = dbus_utils.add_properties(interface_xml, self.interface_name, self.to_introspection_props())
        return ret

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

    def _check_prop(self, property_name):
        if property_name not in self.props_data:
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

    def set(self, interface_name, property_name, new_value):
        if self.access_mask(property_name) != 'write':
            raise common.AccessDenied(property_name, interface_name)
        return self._set(interface_name, property_name, new_value)

    # FIXME: track read/write per property
    def access_mask(self, prop_key):
        return 'write'


class BaseObject(dbus.service.Object):
    # Name of the DBus interface provided by this object
    interface_name = common.INTERFACE_BASE
    object_path = common.ROOT_DBUS_PATH

    def __init__(self, conn=None, object_path=None, bus_name=None,
                 base_object_path=None, service_name=None):
        super(BaseObject, self).__init__(conn=conn, object_path=object_path, bus_name=bus_name)
        self.object_path = object_path
        self._props = self._create_props(self.interface_name)
        self.persistent = True

    def _create_props(self, interface_name):
        properties = BaseProperties.create_instance(interface_name, {}, self.PropertiesChanged)
        return properties

    @property
    def props(self):
        return self._props

    @dbus.service.signal(dbus.PROPERTIES_IFACE, signature='sa{sv}as')
    def PropertiesChanged(self, interface_name, changed_properties, invalidated_properties):
        log.debug("Properties Changed emitted.")

    @common.dbus_service_method(
        dbus.PROPERTIES_IFACE,
        in_signature='s',
        out_signature='a{sv}')
    @common.dbus_handle_exceptions
    def GetAll(self, interface_name, sender=None):
        return dbus.Dictionary(self.props.get_all(interface_name=interface_name), signature='sv')

    @common.dbus_service_method(
        dbus.PROPERTIES_IFACE,
        in_signature='ss',
        out_signature='v')
    @common.dbus_handle_exceptions
    def Get(self, interface_name, property_name, sender=None):
        return self.props.get(interface_name=interface_name, property_name=property_name)

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
        self.props.set(interface_name=interface_name, property_name=property_name, new_value=new_value)
