#
# Copyright (c) 2015 Red Hat, Inc.
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

from subscription_manager import base_plugin
requires_api_version = "1.2"

from subscription_manager.plugin.yum import repolib


class YumContentPlugin(base_plugin.SubManPlugin):
    name = "yum_content"

    def update_content_hook(self, conduit):
        conduit.log.debug("YumRepoContentPlugin.update_content_hook")

        action_invoker = repolib.RepoActionInvoker(ent_source=conduit.ent_source)
        conduit.log.debug("yum action_invoker=%s", action_invoker)
        report = action_invoker.update()
        #conduit.log.debug("report=%s", report)
        conduit.reports.add(report)

    def configure_content_hook(self, conduit):
        conduit.log.debug("YumRepoContentPlugin.configure_content_hook")

        action_invoker = repolib.RepoActionInvoker(ent_source=conduit.ent_source,
                                                   content_config=conduit.content_config)

        conduit.log.debug("yum configure_content_hook action_invoker=%s", action_invoker)
        #conduit.log.debug("conduit.content_config BEFORE=%s", conduit.content_config)

        #result = action_invoker.configure()
        action_invoker.configure()

        #conduit.log.debug("yum configure_content_hook result=%s", result)
        #conduit.log.debug("conduit.content_config AFTER=%s", conduit.content_config)

        # FIXME: pass the content config in to the conduit it, modify it, and return it
        #conduit.configure_info = result
