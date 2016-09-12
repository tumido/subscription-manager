import os
import sys
import logging
import decorator
import string

import dbus.service
import dbus.exceptions


log = logging.getLogger(__name__)

NAME_BASE = "com.redhat.RHSM"
VERSION = "1"

# The base of the 'well known name' used for bus and service names, as well
# as interface names and object paths.
#
# "com.redhat.RHSM1"
BUS_NAME = NAME_BASE + VERSION

# The default interface name for objects we share on this service.
INTERFACE_BASE = BUS_NAME

# The root of the objectpath tree for our services.
# Note: No trailing '/'
#
# /com/redhat/RHSM1
ROOT_DBUS_PATH = '/' + string.replace(BUS_NAME, '.', '/')

SERVICE_VAR_PATH = os.path.join('/', 'var', 'lib', 'rhsm', 'cache')
DBUS_SERVICE_CACHE_PATH = os.path.join(SERVICE_VAR_PATH, 'dbus')

MAIN_INTERFACE = INTERFACE_BASE
MAIN_DBUS_PATH = ROOT_DBUS_PATH

REGISTER_INTERFACE = '%s.%s' % (INTERFACE_BASE, 'Register')

CONFIG_INTERFACE = '%s.%s' % (INTERFACE_BASE, 'Config')
CONFIG_DBUS_PATH = '%s/%s' % (ROOT_DBUS_PATH, 'Config')


class RHSM1DBusException(dbus.DBusException):
    """Base exceptions."""
    include_traceback = True
    _dbus_error_name = "%s.Error" % INTERFACE_BASE


class UnknownProperty(dbus.DBusException):
    include_traceback = True

    def __init__(self, property_name):
        super(UnknownProperty, self).__init__(
            "Property '%s' does not exist" % property_name,
            name="org.freedesktop.DBus.Error.UnknownProperty"
        )


class UnknownInterface(dbus.DBusException):
    include_traceback = True

    def __init__(self, interface_name):
        super(UnknownInterface, self).__init__(
            "Interface '%s' is unknown" % interface_name,
            name="org.freedesktop.DBus.Error.UnknownInterface"
        )


class InvalidArguments(dbus.DBusException):
    include_traceback = True

    def __init__(self, argument):
        super(InvalidArguments, self).__init__(
            "Argument '%s' is invalid" % argument,
            name="org.freedesktop.DBus.Error.InvalidArgs"
        )


class AccessDenied(dbus.DBusException):
    include_traceback = True

    def __init__(self, prop, interface):
        super(AccessDenied, self).__init__(
            "Property '%s' isn't exported (or does not exist) on interface: %s" % (prop, interface),
            name="org.freedesktop.DBus.Error.AccessDenied"
        )


class PropertyMissing(dbus.DBusException):
    include_traceback = True

    def __init__(self, prop, interface):
        super(PropertyMissing, self).__init__(
            "Property '%s' does not exist on interface: %s" % (prop, interface),
            name="org.freedesktop.DBus.Error.AccessDenied"
        )


class Failed(dbus.DBusException):
    include_traceback = True

    def __init__(self, msg=None):
        super(Failed, self).__init__(
            msg or "Operation failed",
            name="org.freedesktop.DBus.Error.Failed"
        )


@decorator.decorator
def dbus_handle_exceptions(func, *args, **kwargs):
    """Decorator to handle exceptions, log them, and wrap them if necessary"""
    try:
        ret = func(*args, **kwargs)
        return ret
    except dbus.DBusException as e:
        log.exception(e)
        raise
    except Exception as e:
        log.exception(e)
        trace = sys.exc_info()[2]
        raise RHSM1DBusException("%s: %s" % (type(e).__name__, str(e))), None, trace


def dbus_service_method(*args, **kwargs):
    kwargs.setdefault("sender_keyword", "sender")
    return dbus.service.method(*args, **kwargs)
