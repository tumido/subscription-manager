import os
import rhsmlib.dbus as common_constants

SUB_SERVICE_NAME = "Facts"

# com.redhat.RHSM1.Facts
FACTS_DBUS_NAME = common_constants.BUS_NAME + '.' + SUB_SERVICE_NAME

# also, com.redhat.RHSM1.Facts
FACTS_DBUS_INTERFACE = common_constants.BUS_NAME + '.' + SUB_SERVICE_NAME

# /com/redhat/RHSM1/Facts
FACTS_DBUS_PATH = common_constants.ROOT_DBUS_PATH + '/' + SUB_SERVICE_NAME

FACTS_VERSION = "1.1e1"
FACTS_NAME = "Red Hat Subscription Manager facts."

FACTS_CACHE_FILE = os.path.join(common_constants.DBUS_SERVICE_CACHE_PATH, FACTS_DBUS_NAME)
# How long the facts cache is valid for in seconds
FACTS_CACHE_DURATION = 240

# policy kit
# PK_ACTION_FACTS_COLLECT = common_constants.PK_ACTION_PREFIX + '.' + SUB_SERVICE_NAME + '.' + 'collect'
