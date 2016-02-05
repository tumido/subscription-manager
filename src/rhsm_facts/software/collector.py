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

# TODO: replace all this with . and relative imports
from rhsm_facts.software import rhn
from rhsm_facts.software import uname
from rhsm_facts.software import distribution

CERT_VERSION = "3.2"


class SoftwareCollector(object):
    def __init__(self):
        self.facts = {}

    def collect(self, collected_facts=None):
        new_facts = {}

        # Set the preferred entitlement certificate version:
        new_facts.update({"system.certificate_version": CERT_VERSION})
        collected_facts.update(new_facts)

        rhn_facts = rhn.RHN().collect(collected_facts)
        collected_facts.update(rhn_facts)

        uname_facts = uname.Uname().collect(collected_facts)
        collected_facts.update(uname_facts)

        distribution_facts = distribution.Distribution().collect(collected_facts)
        collected_facts.update(distribution_facts)

        return collected_facts
