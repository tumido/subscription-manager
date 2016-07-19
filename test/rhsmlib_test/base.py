import os
import sys
import unittest
import subprocess
import dbus
import optparse
import logging
import time
import signal

from rhsmlib.dbus.server import Server
from rhsmlib import import_class
from rhsmlib import dbus as common


class DBusObjectTest(unittest.TestCase):
    def setUp(self):
        self.bus_name = common.BUS_NAME
        command = ['python', __file__, '-n', self.bus_name, '-b', 'dbus.SessionBus']

        object_classes = self.dbus_objects()
        for clazz in object_classes:
            command.append(clazz.__module__ + "." + clazz.__name__)

        env = os.environ.copy()
        # Set the python path with everything that nose has already loaded
        env['PYTHONPATH'] = ":".join(sys.path)
        self.dbus_process = subprocess.Popen(command, env=env)
        time.sleep(0.5)

        self.postServerSetUp()

    def tearDown(self):
        os.kill(self.dbus_process.pid, signal.SIGTERM)
        time.sleep(0.2)

    def dbus_objects(self):
        raise NotImplementedError('Subclasses should define what DBus objects to test')

    def postServerSetUp(self):
        # Subclasses are free to implement this method to create dbus proxies for testing
        pass


def load_bus_class(option, opt_str, value, parser):
    clazz = import_class(value)
    parser.values.bus = clazz


def main(options, args):
    if not args:
        raise RuntimeError("You must provide DBus Object classes as arguments")
    object_classes = []

    for clazz in args:
        object_classes.append(import_class(clazz))

    server = Server(
        bus_class=options.bus,
        bus_name=options.bus_name,
        object_classes=object_classes)
    server.run()


if __name__ == "__main__":
    # Set up root logger for debug purposes
    logger = logging.getLogger('')
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)

    usage = "usage: %prog [options] DBUS_OBJECT_CLASS"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-b", "--bus",
        action="callback", callback=load_bus_class,
        type="string", default=dbus.SessionBus,
        help="Bus to use (e.g. dbus.SessionBus)")
    parser.add_option("-n", "--bus-name")
    (options, args) = parser.parse_args()
    sys.exit(main(options, args))
