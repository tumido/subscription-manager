#!/usr/bin/python
#
# Copyright (c) 2010 Red Hat, Inc.
#
# Authors: Jeff Ortel <jortel@redhat.com>
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

import sys

sys.path.append('/usr/share/rhsm')

from subscription_manager import injection as inj
from subscription_manager.repolib import RepoActionInvoker
from subscription_manager.certlib import Locker
from subscription_manager.utils import chroot
from subscription_manager.injectioninit import init_dep_injection
from subscription_manager import logutil
from rhsm import connection
from rhsm import config


class YumRepoLocker(Locker):
    def __init__(self):
        super(YumRepoLocker, self).__init__()

    def run(self, action):
        # lock.acquire will return False if it would block
        # NOTE: acquire can return None, True, or False
        #       with different meanings.
        nonblocking = self.lock.acquire(blocking=False)
        if nonblocking is False:
            # Could try to grab the pid for the log message, but it's a bit of a race.
            print "Another process has the cert lock. We will not attempt to update certs or repos."
            return 0
        try:
            return action()
        finally:
            self.lock.release()


def update(cache_only):
    """ update entitlement certificates """
    # XXX: Importing inline as you must be root to read the config file
    #from subscription_manager.identity import ConsumerIdentity

    #cert_file = ConsumerIdentity.certpath()
    #key_file = ConsumerIdentity.keypath()

    rl = RepoActionInvoker(cache_only=cache_only, locker=YumRepoLocker())
    report = rl.update()
    print report.repo_file.render_to_string()

    #identity = inj.require(inj.IDENTITY)
    # In containers we have no identity, but we may have entitlements inherited
    # from the host, which need to generate a redhat.repo.
    #if identity.is_valid():
    #    try:
    #        connection.UEPConnection(cert_file=cert_file, key_file=key_file)
    #    #FIXME: catchall exception
    #    except Exception:
    #        # log
    #        return
    #else:
    #    print "Unable to read consumer identity"

    #if config.in_container():
    #    print "Subscription Manager is operating in container mode."

    #rl = RepoActionInvoker(cache_only=cache_only, locker=YumRepoLocker())
    #report = rl.update()
    #print report.repo_file.render_to_string()


def postconfig_hook():
    """ update """
    # register rpm name for yum history recording"
    # yum on 5.7 doesn't have this method, so check for it

    logutil.init_logger_for_yum()

    init_dep_injection()

    # If a tool (it's, e.g., Mock) manages a chroot via 'yum --installroot',
    # we must update entitlements in that directory.
    chroot('/')

    cfg = config.initConfig()
    cache_only = not bool(cfg.get_int('rhsm', 'full_refresh_on_yum'))

    try:
        update(cache_only)
    except Exception, e:
        print str(e)


def main():
    print postconfig_hook()

if __name__ == "__main__":
    main()
