import os
import logging
import time

import dbus

import rhsm.config

from rhsmlib.facts import collector, host_collector, hwprobe, custom
from rhsmlib.dbus import util, base_object
from rhsmlib.dbus.facts import constants

log = logging.getLogger(__name__)


class BaseFacts(base_object.BaseObject):
    interface_name = constants.FACTS_DBUS_INTERFACE
    default_props_data = {}
    facts_collector_class = collector.FactsCollector

    def __init__(self, conn=None, object_path=None, bus_name=None):
        self.dbus_path = object_path
        super(BaseFacts, self).__init__(conn=conn, object_path=object_path, bus_name=bus_name)

        # Default is an empty FactsCollector
        self.facts_collector = self.facts_collector_class()

    def _create_properties(self, interface_name):
        properties = base_object.BaseProperties.create_instance(
            interface_name,
            self.default_props_data,
            self.PropertiesChanged)

        properties.props_data['facts'] = base_object.Property(
            value=dbus.Dictionary({}, signature='ss'),
            value_signature='a{ss}',
            access='read')
        properties.props_data['lastUpdatedTime'] = base_object.Property(
            value=dbus.UInt64(0),
            value_signature='t',
            access='read')
        return properties

    @util.dbus_service_method(dbus_interface=constants.FACTS_DBUS_INTERFACE, out_signature='a{ss}')
    @util.dbus_handle_exceptions
    def GetFacts(self, sender=None):
        collection = self.facts_collector.collect()
        cleaned = dict([(str(key), str(value)) for key, value in collection.data.items()])

        facts_dbus_dict = dbus.Dictionary(cleaned, signature="ss")

        props_iterable = [
            ('facts', facts_dbus_dict),
            ('lastUpdatedTime', time.mktime(collection.collection_datetime.timetuple())),
        ]

        for k, v in props_iterable:
            self.properties[self.interface_name].set(k, v)

        return facts_dbus_dict


class AllFacts(base_object.BaseObject):
    interface_name = constants.FACTS_DBUS_INTERFACE
    default_dbus_path = constants.FACTS_DBUS_PATH

    def __init__(self, conn=None, object_path=None, bus_name=None):
        super(AllFacts, self).__init__(conn=conn, object_path=object_path, bus_name=bus_name)

        # Why aren't we using a dictionary here? Because we want to control the order and OrderedDict
        # isn't in Python 2.6.  By controlling the order and putting CustomFacts last, we can ensure
        # that users can override any fact.
        collector_definitions = [
            ("Host", HostFacts),
            ("Hardware", HardwareFacts),
            ("Custom", CustomFacts),
        ]

        self.collectors = []
        for path, clazz in collector_definitions:
            sub_path = self.default_dbus_path + "/" + path
            self.collectors.append(
                (path, clazz(conn=conn, object_path=sub_path, bus_name=bus_name))
            )

    @util.dbus_service_method(dbus_interface=constants.FACTS_DBUS_INTERFACE, out_signature='a{ss}')
    @util.dbus_handle_exceptions
    def GetFacts(self, sender=None):
        results = {}
        for name, fact_collector in self.collectors:
            results.update(fact_collector.GetFacts())
        return results


class HostFacts(BaseFacts):
    persistent = True
    default_props_data = {
        'version': constants.FACTS_VERSION,
        'name': constants.FACTS_NAME,
    }

    def __init__(self, conn=None, object_path=None, bus_name=None):
        super(HostFacts, self).__init__(conn=conn, object_path=object_path, bus_name=bus_name)
        self.facts_collector = host_collector.HostCollector()


class HardwareFacts(BaseFacts):
    persistent = True
    default_props_data = {
        'version': constants.FACTS_VERSION,
        'name': constants.FACTS_NAME,
    }

    def __init__(self, conn=None, object_path=None, bus_name=None):
        super(HardwareFacts, self).__init__(conn=conn, object_path=object_path, bus_name=bus_name)
        self.facts_collector = hwprobe.HardwareCollector()


class CustomFacts(BaseFacts):
    persistent = True
    default_props_data = {
        'version': constants.FACTS_VERSION,
        'name': constants.FACTS_NAME,
    }

    def __init__(self, conn=None, object_path=None, bus_name=None):
        super(CustomFacts, self).__init__(conn=conn, object_path=object_path, bus_name=bus_name)

        paths_and_globs = [
            (os.path.join(rhsm.config.DEFAULT_CONFIG_DIR, 'facts'), '*.facts'),
        ]
        self.facts_collector = custom.CustomFactsCollector(path_and_globs=paths_and_globs)
