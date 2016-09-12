#! /usr/bin/env python

try:
    import unittest2 as unittest
except ImportError:
    import unittest

import os
import sys
import subprocess
import logging
import time
import signal

from rhsmlib import dbus as common
from rhsmlib.dbus import service_wrapper


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


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)5s [%(name)s:%(lineno)s] %(message)s")
    log = logging.getLogger('')
    log.setLevel(logging.INFO)

    try:
        sys.exit(service_wrapper.main(sys.argv))
    except Exception:
        log.exception("DBus service startup failed")
