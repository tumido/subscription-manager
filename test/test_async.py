#
# Copyright (c) 2010 Red Hat, Inc.
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


import datetime
import fixture

import mock

from subscription_manager.ga import GObject as ga_GObject
import subscription_manager.injection as inj
from subscription_manager.injection import provide
from subscription_manager import async
from subscription_manager import managerlib

import stubs


# some bits we end up calling from list pools
class ListPoolsStubUEP(stubs.StubUEP):
    def getOwner(self, consumeruuid):
        return {'key': 'owner'}

    def getPoolsList(self, consumer, listAll=None, active_on=None, owner=None):
        return []

    def getEntitlementList(self, consumeruuid=None):
        return []


class TestAsyncEverything(fixture.SubManFixture):
    def setUp(self):
        self.callbacks = []
        super(TestAsyncEverything, self).setUp()

        self.mainloop = ga_GObject.MainLoop()

    def setup_failsafe(self):
        ga_GObject.timeout_add(3000, self.quit_on_fail)
        ga_GObject.timeout_add(1000, self.idle_callback)

    def idle_callback(self, *args):
        # hit the refresh a few times, out stubbed
        # refresh doesn't really do anything though
        if len(self.callbacks) > 2:
            self.mainloop.quit()
        return True

    def test_add_task(self):

        self.setup_failsafe()

        ae = async.AsyncEverything()
        ae._success_callback = self.success_callback
        ae._error_callback = self.error_callback
        naptime = 1
        ae.sleep(naptime)

        ae.run()
        self.mainloop.run()

    def test_empty_queues(self):
        self.setup_failsafe()

        # add no tasks
        ae = async.AsyncEverything()
        ae.run()
        self.mainloop.run()

    def test_exception_in_task_method(self):
        self.setup_failsafe()

        ae = async.AsyncEverything()
        ae._success_callback = self.success_callback
        # use callback that asserts

        def error_callback(retval, error):
            self.log.debug(type(error[0]))
            self.log.debug('message=%s', error[1].message)
            self.assertTrue(isinstance(error[0], Exception))
            self.assertEquals('base exception with no usefgul info.', error[1].message)
            raise error[1]
            #self.mainloop.quit()

        ae._error_callback = error_callback

        ae.throw_an_exception()
        ae.run()
        self.mainloop.run()

    def error_callback(self, retval, error):
        self.log.debug("retval=%s", retval)
        self.log.debug("error=%s", error)
        self.callbacks.append(retval)
        self.mainloop.quit()

    def success_callback(self, retval, error):
        self.log.debug("retval=%s", retval)
        self.log.debug("error=%s", error)
        self.callbacks.append(retval)
        self.mainloop.quit()

    def stub_success_callback(self, retval, error):
        self.log.debug("stub_success. This is not expected to be called.")

    def quit_on_fail(self):
        self.log.debug('failed, timeout')
        self.mainloop.quit()


class TestAsyncPool(fixture.SubManFixture):
    def setUp(self):
        self.callbacks = []
        super(TestAsyncPool, self).setUp()

    def thread_queue_callback(self, data, error):
        self.callbacks.append((data, error))

    def idle_callback(self, *args):
        # hit the refresh a few times, out stubbed
        # refresh doesn't really do anything though
        self.ap.refresh(datetime.date.today(), self.thread_queue_callback)
        if len(self.callbacks) > 3:
            self.mainloop.quit()
        return True

    def _create_async_pool(self):
        provide(inj.CP_PROVIDER, stubs.StubCPProvider())
        inj.provide(inj.PROD_DIR, stubs.StubProductDirectory())
        inj.provide(inj.ENT_DIR, stubs.StubEntitlementDirectory())
        inj.provide(inj.CERT_SORTER, stubs.StubCertSorter())

        self.pool_stash = \
                managerlib.PoolStash()

        self.ap = async.AsyncPool(self.pool_stash)

        # add a timeout and a idle handler
        self.idle = ga_GObject.idle_add(self.ap.refresh, datetime.date.today(), self.idle_callback)
        self.timer = ga_GObject.timeout_add(50, self.idle_callback)
        self.mainloop = ga_GObject.MainLoop()

    def test(self):
        self._create_async_pool()

        self.mainloop.run()
        # verify our callback got called a few times
        self.assertTrue(len(self.callbacks) > 3)

    def test_exception(self):
        self._create_async_pool()

        # simulate a exception on pool refresh
        self.pool_stash.refresh = mock.Mock()
        self.pool_stash.refresh.side_effect = IOError()

        self.mainloop.run()
        self.assertTrue(len(self.callbacks) > 3)
        # we should have an exception in the error from the callback
        self.assertTrue(isinstance(self.callbacks[0][1], IOError))
