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

import logging
import os
import platform
import re

from rhsm_facts import exceptions

log = logging.getLogger('rhsm-app.' + __name__)


class DistributionSoftwareCollectorError(exceptions.FactCollectorError):
    pass


class DistributionInfo(object):
    def __init__(self):
        self.data = self.get_distribution_info()

    def get_distribution_info(self):
        distro_keys = ('distribution.name', 'distribution.version',
                       'distribution.id', 'distribution.version.modifier')
        releaseinfo_dict = dict(filter(lambda (key, value): value,
                                zip(distro_keys, self.get_distribution())))
        return releaseinfo_dict

    def _open_release(self, filename):
        return open(filename, 'r')

    # this version os very RHEL/Fedora specific...
    def get_distribution(self):

        version = 'Unknown'
        distname = 'Unknown'
        dist_id = 'Unknown'
        version_modifier = ''

        if os.path.exists('/etc/os-release'):
            f = open('/etc/os-release', 'r')
            os_release = f.readlines()
            f.close()
            data = {'PRETTY_NAME': 'Unknown',
                    'NAME': distname,
                    'ID': 'Unknown',
                    'VERSION': dist_id,
                    'VERSION_ID': version,
                    'CPE_NAME': 'Unknown'}
            for line in os_release:
                split = map(lambda piece: piece.strip('"\n '), line.split('='))
                if len(split) != 2:
                    continue
                data[split[0]] = split[1]

            version = data['VERSION_ID']
            distname = data['NAME']
            dist_id = data['VERSION']
            dist_id_search = re.search('\((.*?)\)', dist_id)
            if dist_id_search:
                dist_id = dist_id_search.group(1)
            # Split on ':' that is not preceded by '\'
            vers_mod_data = re.split('(?<!\\\):', data['CPE_NAME'])
            if len(vers_mod_data) >= 6:
                version_modifier = vers_mod_data[5].lower().replace('\\:', ':')

        elif os.path.exists('/etc/redhat-release'):
            # from platform.py from python2.
            _lsb_release_version = re.compile(r'(.+)'
                                              ' release '
                                              '([\d.]+)'
                                              '\s*(?!\()(\S*)\s*'
                                              '[^(]*(?:\((.+)\))?')
            f = self._open_release('/etc/redhat-release')
            firstline = f.readline()
            f.close()

            m = _lsb_release_version.match(firstline)

            if m is not None:
                (distname, version, tmp_modifier, dist_id) = tuple(m.groups())
                if tmp_modifier:
                    version_modifier = tmp_modifier.lower()

        elif hasattr(platform, 'linux_distribution'):
            (distname, version, dist_id) = platform.linux_distribution()
            version_modifier = 'Unknown'

        return distname, version, dist_id, version_modifier


class Distribution(object):
    def collect(self, collected_facts):
        try:
            distribution_info = DistributionInfo()
        except Exception, e:
            raise DistributionSoftwareCollectorError(e)

        collected_facts.update(distribution_info)
        return collected_facts
