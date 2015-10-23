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

from subscription_manager import base_plugin
requires_api_version = "1.1"

from subscription_manager import repolib


class YumRepoContentPlugin(base_plugin.SubManPlugin):
    name = "yum_content"

    def update_content_hook(self, conduit):
        conduit.log.debug("YumRepoContentPlugin.update_content_hook")

        action_invoker = repolib.RepoUpdateActionCommand()
        report = action_invoker.perform()
        conduit.reports.add(report)
