#
# Copyright (c) 2014 Red Hat, Inc.
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

from subscription_manager import base_action_client
from subscription_manager import certlib
from subscription_manager import utils
from subscription_manager.model.ent_cert import EntitlementDirEntitlementSource

import subscription_manager.injection as inj

log = logging.getLogger('rhsm-app.' + __name__)


class ContentPluginActionReport(certlib.ActionReport):
    """Aggragate the info reported by each content plugin.

    Just a set of reports that include info about the content
    plugin that created it.
    """
    name = "Content Plugin Reports"

    def __init__(self):
        super(ContentPluginActionReport, self).__init__()
        self.reports = set()

    def add(self, report):
        # report should include info about what plugin generated it
        self.reports.add(report)


class ContentPluginActionCommand(object):
    """An ActionCommand used to wrap 'content_update' plugin invocations.

    args:
        content_plugin_runner: a PluginHookRunner created with
              PluginManager.runiter('content_update').runiter()

    perform() runs the PluginHookRunner and returns the ContentActionReport
      that PluginHookRunner.run() adds to the content plugin conduit.
    """
    def __init__(self, content_plugin_runner):
        self.runner = content_plugin_runner

    def perform(self):
        self.runner.run()
        # Actually a set of reports...
        return self.runner.conduit.reports


class ContentPluginConfigureActionCommand(object):
    def __init__(self, content_plugin_runner):
        self.runner = content_plugin_runner

    def perform(self):
        # run the plugin hook...
        self.runner.run()
        # Actually a set of reports...
        return self.runner.conduit.content_config


class ContentPluginActionInvoker(certlib.BaseActionInvoker):
    """ActionInvoker for ContentPluginActionCommands."""
    def __init__(self, content_plugin_runner):
        """Create a ContentPluginActionInvoker to wrap content plugin PluginHookRunner.

        Pass a PluginHookRunner to ContentPluginActionCommand. Do the
        normal ActionInvoker tasks and collect ActionReports.

        args:
            content_plugin_runner: a PluginHookRunner created with
              PluginManager.runiter('content_update').runiter()
        """
        super(ContentPluginActionInvoker, self).__init__()
        self.runner = content_plugin_runner

    def _do_update(self):
        action = ContentPluginActionCommand(self.runner)
        return action.perform()

    def configure(self, configured_infos=None):
        action = ContentPluginConfigureActionCommand(self.runner)
        return action.perform()


class ConfiguredContentInfo(object):
    def __init__(self, content_type=None, repos=None):
        self.content_type = content_type
        self.repos = repos or []

    def __repr__(self):
        return "ConfiguredContentInfo(content_type=%s, repos=%s)" % (self.content_type,
                                                                    self.repos)


class ContentActionClient(base_action_client.BaseActionClient):

    def __init__(self):
        super(ContentActionClient, self).__init__()
        self.configure_actions = self._get_configure_actions()

    def _get_libset(self):
        """Return a generator that creates a ContentPluginAction* for each update_content plugin.

        The iterable return includes the yum repo action invoker, and a ContentPluginActionInvoker
        for each plugin hook mapped to the 'update_content_hook' slot.
        """

        plugin_manager = inj.require(inj.PLUGIN_MANAGER)

        content_plugins_reports = ContentPluginActionReport()

        # Ent dir is our only source of entitlement/content info atm
        # NOTE: this is created and populated with the content of
        # the ent dir before the plugins are run and it doesn't
        # update.
        ent_dir_ent_source = EntitlementDirEntitlementSource()

        for runner in plugin_manager.runiter('update_content',
                                             reports=content_plugins_reports,
                                             ent_source=ent_dir_ent_source):
            invoker = ContentPluginActionInvoker(runner)
            yield invoker

    def _get_configure_actions(self):
        log.debug("_get_configure_actions")
        plugin_manager = inj.require(inj.PLUGIN_MANAGER)

        ent_dir_ent_source = EntitlementDirEntitlementSource()

        # new Empty Content config, plugins will eventually populate it, read it, modify it
        content_config = utils.DefaultDict(dict)

        for runner in plugin_manager.runiter('configure_content',
                                             ent_source=ent_dir_ent_source,
                                             content_config=content_config):
            invoker = ContentPluginActionInvoker(runner)
            log.debug("_get_configure_actions invoker=%s", invoker)
            yield invoker

    def configure(self):
        #configure_infos = []
        res = None
        for configure_action in self.configure_actions:
            log.debug("running configure_action=%s configure()", configure_action)
            # We could just pass the subset of content config associated with the content types the
            # plugin knows. But it seems more useful for each plugin to be able to see all of the existing
            # content config.
            res = configure_action.configure()
            #content_config[content_type] = res

        log.debug("res=%s", res)
        return res or None
