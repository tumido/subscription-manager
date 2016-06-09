
import logging

from rhsmlib.facts import host_collector

from rhsmlib.dbus.facts import cache
from rhsmlib.dbus.facts import constants
from rhsmlib.dbus.facts import base_facts

log = logging.getLogger(__name__)


class FactsHostCacheFile(cache.JsonFileCache):
    CACHE_FILE = constants.FACTS_HOST_CACHE_FILE
    default_duration_seconds = constants.FACTS_HOST_CACHE_DURATION


class FactsHost(base_facts.BaseFacts):
    persistent = True
    default_props_data = {
        'version': constants.FACTS_HOST_VERSION,
        'name': constants.FACTS_HOST_NAME,
    }
    default_dbus_path = constants.FACTS_HOST_DBUS_PATH

    def __init__(self, conn=None, object_path=None, bus_name=None):
        log.debug("Initializing FactsHost")
        super(FactsHost, self).__init__(conn=conn, object_path=object_path, bus_name=bus_name)

        host_cache = FactsHostCacheFile()
        self.facts_collector = host_collector.HostCollector(cache=host_cache)
