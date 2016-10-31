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
import gettext
import socket
import json
import logging
import dbus.service

from rhsmlib.dbus import constants, exceptions, dbus_utils

from subscription_manager import managerlib
from rhsm import connection

from subscription_manager import injection as inj

_ = gettext.gettext
log = logging.getLogger(__name__)


class PrivateService(dbus.service.Object):
    """ The base class for service objects to be exposed on either a private connection
        or a bus."""
    _interface_name = None
    _default_dbus_path = constants.ROOT_DBUS_PATH
    _default_dbus_path += ("/" + _interface_name) if _interface_name else ""
    _default_bus_name = constants.BUS_NAME

    def __init__(self, conn=None, bus=None, object_path=None):
        # Note that the bus parameter is not a bus name but an actual instance of a Bus.  E.g. dbus.SystemBus
        if object_path is None or object_path == "":
            # If not given a path to be exposed on, use class defaults
            _interface_name = self.__class__._interface_name or ""
            if _interface_name:
                object_path = "/" + _interface_name.replace('.', '/')
            else:
                object_path = self.__class__._default_dbus_path

        bus_name = None
        if bus is not None:
            # If we are passed in a bus, try to claim an appropriate bus name
            bus_name = dbus.service.BusName(self.__class__._default_bus_name, bus)

        super(PrivateService, self).__init__(object_path=object_path, conn=conn, bus_name=bus_name)


class RegisterService(PrivateService):
    _interface_name = constants.REGISTER_INTERFACE

    @dbus.service.method(dbus_interface=constants.REGISTER_INTERFACE,
                                    in_signature='sssa{sv}',
                                    out_signature='a{sv}')
    def register(self, username, password, org, options):
        """
        This method registers the system using basic auth
        (username and password for a given org).
        For any option that is required but not included the default will be
        used.

        Options is a dict of strings that modify the outcome of this method.
        """
        # TODO: Read from config if needed
        options = RegisterService._validate_register_options(options)
        # We have to convert dictionaries from the dbus objects to their
        # python equivalents. Seems like the dbus dictionaries don't work
        # in quite the same way as regular python ones.
        options = dbus_utils.dbus_to_python(options)

        # TODO: Facts collection, We'll need facts exposed as a service like
        #       the config to achieve this.
        installed_mgr = inj.require(inj.INSTALLED_PRODUCTS_MANAGER)

        options['username'] = username
        options['password'] = password
        cp = RegisterService._get_uep_from_options(options)
        registration_output = cp.registerConsumer(
            name=options['name'],
            owner=org,
            installed_products=installed_mgr.format_for_server(),
            content_tags=installed_mgr.tags
        )
        installed_mgr.write_cache()
        registration_output['content'] = RegisterService._persist_and_sanitize_consumer(
            registration_output['content']
        )
        return dbus_utils.dict_to_variant_dict(registration_output)

    @dbus.service.method(dbus_interface=constants.REGISTER_INTERFACE,
        in_signature='sa(s)a{ss}',
        out_signature='a{sv}')
    def register_with_activation_keys(self, org, activation_keys, options):
        """ This method registers a system with the given options, using
            an activation key."""
        # NOTE: We could probably manage doing this in one method with the use
        #       of variants in the in_signature (but I'd imagine that might be
        #       slightly more difficult to unit test)
        options = RegisterService._validate_register_options(options)

        options = dbus_utils.dbus_to_python(options)

        cp = RegisterService._get_uep_from_options(options)
        installed_mgr = inj.require(inj.INSTALLED_PRODUCTS_MANAGER)

        registration_output = cp.registerConsumer(
            name=options['name'],
            keys=activation_keys,
            owner=org,
            installed_products=installed_mgr.format_for_server(),
            content_tags=installed_mgr.tags
        )

        installed_mgr.write_cache()
        registration_output['content'] = RegisterService._persist_and_sanitize_consumer(registration_output['content'])
        return dbus_utils.dict_to_variant_dict(registration_output)

    @staticmethod
    def _get_uep_from_options(options):
        return connection.UEPConnection(
            username=options.get('username', None),
            password=options.get('password', None),
            host=options.get('host', None),
            ssl_port=connection.safe_int(options.get('port', None)),
            handler=options.get('handler', None),
            insecure=options.get('insecure', None),
            proxy_hostname=options.get('proxy_hostname', None),
            proxy_port=options.get('proxy_port', None),
            proxy_user=options.get('proxy_user', None),
            proxy_password=options.get('proxy_password', None),
            restlib_class=connection.BaseRestLib
        )

    @staticmethod
    def _persist_and_sanitize_consumer(consumer_json):
        """ Persists consumer and removes unnecessary keys """
        consumer = json.loads(consumer_json,
            object_hook=dbus_utils._decode_dict)
        managerlib.persist_consumer_cert(consumer)

        del consumer['idCert']

        return json.dumps(consumer)

    @staticmethod
    def is_registered():
        return inj.require(inj.IDENTITY).is_valid()

    @staticmethod
    def _validate_register_options(options):
        # TODO: Rewrite the error messages to be more dbus specific
        # From managercli.RegisterCommand._validate_options
        error_msg = None
        autoattach = options.get('autosubscribe') or options.get('autoattach')
        if RegisterService.is_registered() and not options.get('force'):
            error_msg = _("This system is already registered. Add force to options to override.")
        elif (options.get('consumername') == ''):
            error_msg = _("Error: system name can not be empty.")
        elif (options.get('username') and options.get('activation_keys')):
            error_msg = _("Error: Activation keys do not require user credentials.")
        elif (options.get('consumerid') and options.get('activation_keys')):
            error_msg = _("Error: Activation keys can not be used with previously registered IDs.")
        elif (options.get('environment') and options.get('activation_keys')):
            error_msg = _("Error: Activation keys do not allow environments to be specified.")
        elif (autoattach and options.get('activation_keys')):
            error_msg = _("Error: Activation keys cannot be used with --auto-attach.")
        # 746259: Don't allow the user to pass in an empty string as an activation key
        elif (options.get('activation_keys') and '' in options.get('activation_keys')):
            error_msg = _("Error: Must specify an activation key")
        elif (options.get('service_level') and not autoattach):
            error_msg = _("Error: Must use --auto-attach with --servicelevel.")
        elif (options.get('activation_keys') and not options.get('org')):
            error_msg = _("Error: Must provide --org with activation keys.")
        elif (options.get('force') and options.get('consumerid')):
            error_msg = _("Error: Can not force registration while attempting to recover registration with consumerid. Please use --force without --consumerid to re-register or use the clean command and try again without --force.")

        if error_msg:
            raise exceptions.Failed(msg=error_msg)
        if not 'name' in options or not options['name']:
            options['name'] = socket.gethostname()
        return options
