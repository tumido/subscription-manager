#
# Async wrapper module for managerlib methods, with glib integration
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

import Queue
import logging
import sys
import threading
import time
import gettext

from subscription_manager.ga import GObject as ga_GObject
from subscription_manager.entcertlib import Disconnected
from subscription_manager.managerlib import fetch_certificates
from subscription_manager.injection import IDENTITY, \
        PLUGIN_MANAGER, CP_PROVIDER, require

_ = gettext.gettext


log = logging.getLogger('rhsm-app.' + __name__)


# Worker/AsyncAction
# TheadPool
# Tasks
#   (has a) TaskQueue, add workers to TaskQueue
#   (has a) ResultsQueue
#   (has a) ThreadPool consumes worker from TaskQueue
#   (has a) ResultsWatcher consumes results from ResultsQueue
#           idle_add's callbacks (and results or errors) to mainthread mainloop
#
# Worker/AsyncAction
#     worker runs target method
#     returns or throws exception
#     worker target method add results (callbacks, data, errors) to ResultsQueue
#
# NetworkTasks could have a small thread pool
# IOTasks
#   CacheTasks - read/write cached objects to disk
#              - join() before exit?

class Task(object):
    def __init__(self,
                 func,
                 func_args=None,
                 success_callback=None,
                 error_callback=None,
                 thread_name=None):
        self.func = func or ()
        self.func_args = func_args
        self.success_callback = success_callback
        self.error_callback = error_callback
        self.thread_name = thread_name

    def __repr__(self):
        return "Task(func=%s, func_args=%s, success_callback=%s, error_callback=%s, thread_name=%s)" % \
            (self.func, self.func_args, self.success_callback, self.error_callback, self.thread_name)


class IdleQueue(Queue.Queue):
    def _put_idle_callback(self, item):
        self.put(item)
        return False

    def put_idle(self, item):
        """Put an item into queue from _put_idle_callback in main thread."""
        ga_GObject.idle_add(self._put_idle_callback, item)


class TaskQueue(IdleQueue):
    pass


class ResultQueue(IdleQueue):
    pass


def main_idle_add(func):
    """Decorator method which ensures every call of the decorated function to be
       executed in the context of Gobject main loop even if called from a non-main
       thread. The new method does not wait for the callback to finish.

       The return of the method is also ignored. Use callbacks if needed.
       The value returned is the id of the added idle handler.
    """

    def _idle_method(args, kwargs):
        """This method contains the code for the main loop to execute.
        """
        func(*args, **kwargs)
        return False

    def _call_method(*args, **kwargs):
        """The new body for the decorated method.
        """
        idle_handler_id = ga_GObject.idle_add(_idle_method, args, kwargs)
        return idle_handler_id

    return _call_method


class TaskWorkerThread(threading.Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs={}):
        pass


class QueueConsumer(object):
    def __init__(self, queue):
        self.queue = queue
        self._idle_callback_id = None
        self._consuming = False
        self.log = logging.getLogger(__name__ + '.' +
                                     self.__class__.__name__)

    def queue_get_idle_handler(self):
        """Called from mainloop to poll results queue for new results.

        Then idle_adds the results callback and/or error to the main thread main loop
        via self._process_callback."""

        #log.debug("idle hands, etc")

        # Everything in here runs in the main thread.
        try:
            queue_item = self.queue.get(block=False)
            self.log.debug("got a queue_item in idle_callback")
            self.queue.task_done()
            self._process_queue_item(queue_item)
        except Queue.Empty:
            # ??? Does Queue.task_done() need to be called on empty queue?
            # we were setup with a idle_callback, but so far the queue is empty, but
            # keep trying
            if self._consuming:
                #log.debug("queue is empty, but we are consume...")
                return True

            #log.debug("queue is empty, and we are not expecting to consumer, so stop.")
            # remove the callback on empty
            self._idle_callback_id = None
            return False
        except Exception, e:
            self.log.debug("idle_callback exception")
            self.log.exception(e)
            raise

        #self._consuming = False
        return True

    def consume(self):
        """Start consuming the queue via a self.idle_callback.

        When the queue is empty, the idle_callback returns
        True, but it always returns true, unless self."""
        self._consuming = True
        if not self._idle_callback_id:
            self._idle_callback_id = ga_GObject.idle_add(self.queue_get_idle_handler)

        return self._idle_callback_id

    def _process_queue_item(self, queue_item):
        """Call for each item getting from the queue.

        This should call self.queue.task_done or super()'s."""
        pass


class TaskQueueConsumer(QueueConsumer):

    def __init__(self, task_queue, result_queue):
        super(TaskQueueConsumer, self).__init__(task_queue)
        self.workers = []
        self.result_queue = result_queue

    def _process_queue_item(self, queue_item):
        """queue_item is a Task object to have a thread created for and run."""

        task = queue_item
        # self.log.debug("About to spin off a thread for task=%s", task)
        threading.Thread(target=self._target_method,
                         args=(task.func, task.func_args, task.success_callback, task.error_callback),
                         name=task.thread_name).start()

        # self.log.debug("hopefully started a thread for task=%s", task)

    def _target_method(self, func, func_args, success_callback, error_callback):
        try:
            retval = func(*func_args)
            self.log.debug("success_callback=%s, retval=%s", success_callback, retval)
            # FIXME: add to queue from main thread via idle_callback
            self.result_queue.put_idle((success_callback, retval, None))
        except Exception, e:
            self.log.exception(e)
            self.log.debug("busted in target_method")
            self.result_queue.put_idle((error_callback, None, sys.exc_info()))

    def wait_completion(self):
        self.queue.join()


class ResultsQueueConsumer(QueueConsumer):
    """Consumers results, and idle_adds the callback and data to mainloop."""

    def _process_queue_item(self, queue_item):
        (callback, retval, error) = queue_item
        self.log.debug("cb=%s", callback)
        self.log.debug("retval=%s", retval)
        self.log.debug("error=%s", error)
        ga_GObject.idle_add(callback, retval, error)


class Tasks(object):
    def __init__(self):
        self.task_queue = TaskQueue()
        self.result_queue = ResultQueue()
        self.task_queue_consumer = TaskQueueConsumer(self.task_queue, self.result_queue)
        self.result_queue_consumer = ResultsQueueConsumer(self.result_queue)
        self.log = logging.getLogger(__name__ + '.' +
                                     self.__class__.__name__)

        self.log.debug("Tasks init")

    def add(self, task):
        """task is a Task. Add to queue and start consuming."""
        self.task_queue.put(task)
        self.task_queue_consumer.consume()
        self.log.debug("added task (to become thread=%s)", task.thread_name)

    # TODO: start from AsyncEverything.run or a idle callback version of it
    def run(self):
        self.task_queue_consumer.consume()
        self.result_queue_consumer.consume()


class AsyncEverything(object):
    """Base class for async handling of tasks.

    You must create this class from the main thread.
    It also requires that the mainloop runs at some point."""

    def __init__(self):
        self.log = logging.getLogger(__name__ + '.' +
                                     self.__class__.__name__)
        self.log.debug("AsyncEverything init")
        self.tasks = Tasks()

    @main_idle_add
    def run(self):
        self.tasks.run()

    # TODO: we'll want to be able to pass in callbacks as args, so likely
    #       add a decorator to do that.
    def _success_callback(self, retval, error):
        if error:
            self.log.debug("weird...")
            raise Exception('Ugh, that is totally weird')

        self.log.debug("_success_callback retval=%s", retval)

    def _error_callback(self, retval, error):
        if not error:
            self.log.debug("This is the error_callback, why is there no error? retval=%s error=%s", retval, error)
            raise Exception('We were hoping, even wishing for an error')

        self.log.debug("_error_callback retval=%s", retval)

    def add_task(self, target_method,
                 target_args=None, success_callback=None, error_callback=None, thread_name=None):
        # empty args tuple by default
        target_args = target_args or ()
        success_callback = success_callback or self._success_callback
        error_callback = error_callback or self._error_callback

        task = Task(target_method, target_args,
                    success_callback, error_callback,
                    thread_name)
        self.log.debug("add_task task=%s", task)
        self.tasks.add(task)

    def _sleep(self, how_long):
        """An example of a method that ends up being the threads target."""

        self.log.debug("sooooooooooooo sleeeepy")
        time.sleep(how_long)
        self.log.debug("better now")

        return 'slept for %s seconds' % how_long

    def sleep(self, how_long):
        """An example of a method that becomes a Task.

        It sets up the target code, args, callbacks, and thread name."""
        self.log.debug("AsyncEverything.sleep")
        #self.add_task(self._sleep, (how_long,), thread_name='SleepThread')
        self.add_task(time.sleep, (how_long,), thread_name='SleepThread')

    def _throw_an_exception(self):
        self.log.debug("Throwing an exception because you asked for it.")
        raise Exception('base exception with no useful info.')

    def throw_an_exception(self):
        self.add_task(self._throw_an_exception, thread_name='ThrowAnExceptionThread')


class AsyncPool(object):

    def __init__(self, pool):
        self.pool = pool
        self.queue = Queue.Queue()

    def _run_refresh(self, active_on, callback, data):
        """
        method run in the worker thread.
        """
        try:
            self.pool.refresh(active_on)
            self.queue.put((callback, data, None))
        except Exception, e:
            self.queue.put((callback, data, e))

    def _watch_thread(self):
        """
        glib idle method to watch for thread completion.
        runs the provided callback method in the main thread.
        """
        try:
            (callback, data, error) = self.queue.get(block=False)
            callback(data, error)
            return False
        except Queue.Empty:
            return True

    def refresh(self, active_on, callback, data=None):
        """
        Run pool stash refresh asynchronously.
        """
        ga_GObject.idle_add(self._watch_thread)
        threading.Thread(target=self._run_refresh, name="AsyncPoolRefreshThread",
                args=(active_on, callback, data)).start()


class AsyncBind(object):

    def __init__(self, certlib):
        self.cp_provider = require(CP_PROVIDER)
        self.identity = require(IDENTITY)
        self.plugin_manager = require(PLUGIN_MANAGER)
        self.certlib = certlib

    def _run_bind(self, pool, quantity, bind_callback, cert_callback, except_callback):
        try:
            self.plugin_manager.run("pre_subscribe", consumer_uuid=self.identity.uuid,
                    pool_id=pool['id'], quantity=quantity)
            ents = self.cp_provider.get_consumer_auth_cp().bindByEntitlementPool(self.identity.uuid, pool['id'], quantity)
            self.plugin_manager.run("post_subscribe", consumer_uuid=self.identity.uuid, entitlement_data=ents)
            if bind_callback:
                ga_GObject.idle_add(bind_callback)
            fetch_certificates(self.certlib)
            if cert_callback:
                ga_GObject.idle_add(cert_callback)
        except Exception, e:
            ga_GObject.idle_add(except_callback, e)

    def _run_unbind(self, serial, selection, callback, except_callback):
        """
        Selection is only passed to maintain the gui error message.  This
        can be removed, because it doesn't really give us any more information
        """
        try:
            self.cp_provider.get_consumer_auth_cp().unbindBySerial(self.identity.uuid, serial)
            try:
                self.certlib.update()
            except Disconnected, e:
                pass

            if callback:
                ga_GObject.idle_add(callback)
        except Exception, e:
            ga_GObject.idle_add(except_callback, e, selection)

    def bind(self, pool, quantity, except_callback, bind_callback=None, cert_callback=None):
        threading.Thread(target=self._run_bind, name="AsyncBindBindThread",
                args=(pool, quantity, bind_callback, cert_callback, except_callback)).start()

    def unbind(self, serial, selection, callback, except_callback):
        threading.Thread(target=self._run_unbind, name="AsyncBindUnbindThread",
                args=(serial, selection, callback, except_callback)).start()


class AsyncRepoOverridesUpdate(object):

    def __init__(self, overrides_api):
        self.overrides_api = overrides_api
        self.identity = require(IDENTITY)

    def _load_data(self, success_callback, except_callback):
        try:
            # pull the latest overrides from the cache which will be the ones from the server.
            current_overrides = self.overrides_api.get_overrides(self.identity.uuid) or []

            # Fetch the repositories from repolib without any overrides applied.
            # We do this so that we can tell if anything has been modified by
            # overrides.
            current_repos = self.overrides_api.repo_lib.get_repos(apply_overrides=False)

            self._process_callback(success_callback, current_overrides, current_repos)
        except Exception, e:
            self._process_callback(except_callback, e)

    def _update(self, to_add, to_remove, success_callback, except_callback):
        '''
        Processes the override mapping and sends the overrides to the server for addition/removal.
        '''
        try:
            # TODO: At some point we should look into providing a single API call that can handle
            #       additions and removals in the same call (currently not supported by server).
            current_overrides = None
            if len(to_add) > 0:
                current_overrides = self.overrides_api.add_overrides(self.identity.uuid, to_add)

            if len(to_remove) > 0:
                current_overrides = self.overrides_api.remove_overrides(self.identity.uuid, to_remove)

            if current_overrides:
                self.overrides_api.update(current_overrides)

            # Fetch the repositories from repolib without any overrides applied.
            # We do this so that we can tell if anything has been modified by
            # overrides.
            current_repos = self.overrides_api.repo_lib.get_repos(apply_overrides=False)

            self._process_callback(success_callback, current_overrides, current_repos)
        except Exception, e:
            self._process_callback(except_callback, e)

    def _remove_all(self, repo_ids, success_callback, except_callback):
        try:
            current_overrides = self.overrides_api.remove_all_overrides(self.identity.uuid, repo_ids)
            self.overrides_api.update(current_overrides)

            # Fetch the repositories from repolib without any overrides applied.
            # We do this so that we can tell if anything has been modified by
            # overrides.
            current_repos = self.overrides_api.repo_lib.get_repos(apply_overrides=False)

            self._process_callback(success_callback, current_overrides, current_repos)
        except Exception, e:
            self._process_callback(except_callback, e)

    def _process_callback(self, callback, *args):
        ga_GObject.idle_add(callback, *args)

    def load_data(self, success_callback, failure_callback):
        threading.Thread(target=self._load_data, name="AsyncRepoOverridesUpdateLoadDataThread",
                         args=(success_callback, failure_callback)).start()

    def update_overrides(self, to_add, to_remove, success_callback, except_callback):
        threading.Thread(target=self._update, name="AsyncRepoOverridesUpdateUpdateOverridesThread",
                         args=(to_add, to_remove, success_callback, except_callback)).start()

    def remove_all_overrides(self, repo_ids, success_callback, except_callback):
        threading.Thread(target=self._remove_all, name="AsyncRepoOverridesUpdateRemoveAllOverridesThread",
                         args=(repo_ids, success_callback, except_callback)).start()
