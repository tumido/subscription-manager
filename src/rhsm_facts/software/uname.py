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

from rhsm_facts import exceptions

log = logging.getLogger('rhsm-app.' + __name__)


class UnameSoftwareCollectorError(exceptions.FactCollectorError):
    pass


class UnameInfo(object):
    def __init__(self):
        self.data = self.get_uname_info()

    def get_uname_info(self):

        uname_data = os.uname()
        uname_keys = ('uname.sysname', 'uname.nodename', 'uname.release',
                      'uname.version', 'uname.machine')
        uname_dict = dict(zip(uname_keys, uname_data))
        return uname_dict


def Uname(object):
    def collect(self, collected_facts):
        try:
            uname_info = UnameInfo()
        except Exception, e:
            log.exception(e)
            raise UnameSoftwareCollectorError(e)

        collected_facts.update(uname_info.data)
        return collected_facts
