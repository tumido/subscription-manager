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

from rhsmlib.dbus import constants, server
from subscription_manager.injectioninit import init_dep_injection

from rhsmlib.dbus.objects.private import RegisterService

from functools import partial

log = logging.getLogger(__name__)
init_dep_injection()


class Main(dbus.service.Object):
    default_dbus_path = constants.MAIN_DBUS_PATH

    @dbus.service.method(
        dbus_interface=constants.MAIN_INTERFACE,
        out_signature='s')
    def start_registration(self):
        log.debug('start_registration called')
        server = self._create_registration_server()
        return server.address

    def _disconnect_on_last_connection(self, server, conn):
        log.debug('Checking if server "%s" has any remaining connections', server)
        if server._Server__connections:
            log.debug('Server still has connections')
            return

        log.debug('No connections remain, disconnecting')
        server.disconnect()
        del server

    def _create_registration_server(self):
        log.debug('Attempting to create new server')
        priv_server = server.PrivateServer().create_server([RegisterService])
        priv_server.on_connection_removed.append(partial(self._disconnect_on_last_connection, priv_server))
        log.debug('Server created and listening on "%s"', priv_server.address)
        return priv_server
