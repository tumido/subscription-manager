# Copyright (c) 2011-2015 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
#


CERT_VERSION = "3.2"


class SoftwareCollector(object):
    def __init__(self):
        self.facts = {}

    def collect(self, collected_facts=None):
        new_facts = {}

        # Set the preferred entitlement certificate version:
        new_facts.update({"system.certificate_version": CERT_VERSION})

        collected_facts.update(new_facts)

        # TODO: add rhn check
        return collected_facts