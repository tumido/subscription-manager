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
    """A method to be called later async.

    func and func_args are the method to call (generally as a Thread(target=func)).

    The success and error callbacks are methods to call on success (func completes)
    or error (an Exception was raised). Callbacks are optional, but they are the only
    way to return data from the task.

    thread_name is optional, but if provide will be used for the name of the TaskWorkerThread
    that is started."""
    def __init__(self,
                 func,
                 func_args=None,
                 success_callback=None,
                 error_callback=None,
                 thread_name=None):
        self.func = func
        self.func_args = func_args or ()
        self.success_callback = success_callback
        self.error_callback = error_callback
        self.thread_name = thread_name

    def __repr__(self):
        return "Task(func=%s, func_args=%s, success_callback=%s, error_callback=%s, thread_name=%s)" % \
            (self.func.__name__, self.func_args,
             self.success_callback.__name__,
             self.error_callback.__name__, self.thread_name)


class QueueSentinel(Exception):
    consuming_state = None

    def __repr__(self):
        return '%s(consuming_state=%s)' % (self.__class__.__name__, self.consuming_state)


class QueueStartSentinel(QueueSentinel):
    consuming_state = True


class QueueStopSentinel(QueueSentinel):
    consuming_state = False


class IdleQueue(Queue.Queue, object):
    """A Queue that includes a put_idle() for deferring a put until mainloop runs idle handlers."""
    def _put_idle_callback(self, item):
        self.put(item)
        return False

    def put_idle(self, item):
        """Put an item into queue from _put_idle_callback in main thread."""
        ga_GObject.idle_add(self._put_idle_callback, item)

    def get(self, block, timeout=None):
        ret = super(IdleQueue, self).get(block=block, timeout=timeout)

        # Is the item in the queue a sentinel, reraise it, so we
        # can treat queue sentinels like Queue.Empty
        if isinstance(ret, QueueSentinel):
            raise ret

        return ret


class TaskQueue(IdleQueue):
    """IdleQueue containing Task() objects, waiting to be run."""
    pass


class WorkerQueue(IdleQueue):
    """IdleQueue containing TaskWorkerThread objects, waiting to be run."""
    pass


class ResultQueue(IdleQueue):
    """IdleQueue container the results from consuming and running items from a TaskQueue."""
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


class RunAsTask:
    def __init__(self, obj):
        self.obj = obj
        self.log = logging.getLogger('RunAsTask')
        self.log.debug("init")
        self.log.debug("init obj=%s", obj)

    def __call__(self, *args, **kwargs):
        self.log.debug("self.obj=%s", self.obj)
        self.log.debug("self=%s, args=%s, kwargs=%s", self, args, kwargs)
        self.obj(*args, **kwargs)


class TaskWorkerThread(threading.Thread):
    """Thread is the threading.Thread subclass used by AsyncEverything."""
    pass


class QueueConsumer(object):
    """Consume a IdleQueue via a idle_handler.

    Items can be added to self.queue.

    To start processing the queue, call self.consume().

    As the idle loop calls QueueConsumer.queue_get_idle_handler, items
    in QueueConsumer.queue are fetched via the queues .get() amd proccessed
    via _process_queue_item().

    _process_queue_item() needs to be non-blocking.

    When the queue is empty, queue_get_idle_handler will return False,
    removing it from the mainloops idle sources. This will stop the consuming
    of the queue. WHen self.consume() is called, the queue_get_idle_handler
    will be added to the idle sources and will continue to be called even
    on a empty queue until self._consuming if False (ie, via self.stop()).
    """
    def __init__(self, queue):
        self.queue = queue

        # Likely should be a semaphore, but then we only manipulate
        # the queue from the mainthread.
        self._consuming = False
        self.log = logging.getLogger(__name__ + '.' +
                                     self.__class__.__name__)

    def consume_one(self):
        self.log.debug("consumer_one")
        try:
            queue_item = self.queue.get(block=False)
        except Queue.Empty:
            if self._consuming:
                return True
            # Tell Tasks we are empty and have been told to stop.
            return False
        except QueueSentinel, qs:
            self.log.debug("QueueSentinel self._consuming=%s", self._consuming)
            self.log.debug("QueueSentinel qs=%s type=%s", repr(qs), type(qs))
            self.queue.task_done()
            return self._process_queue_sentinel(qs)
        except Exception, e:
            self.log.debug("consume_one exception")
            self.log.exception(e)
            raise

        self.log.debug("got a queue_item in idle_callback, queue_item=%s", queue_item)

        self.queue.task_done()
        self._process_queue_item(queue_item)

        return True

    def start(self):
        self.log.debug("start")
        self.queue.put_idle(QueueStartSentinel())

    def stop(self):
        self.log.debug("stop")
        self.queue.put_idle(QueueStopSentinel())

    def _process_queue_sentinel(self, sentinel):
        # Set _consuming based on the sentinel, so the next consume_one gets
        # the new _consuiming state. Ie, if we got a QueueStopSentinel, on the
        # next consume_one, self._consuming will be False and the Queue is empty, so
        # we return False (indicating that we've seen a stop and the queue is empty).
        self.log.debug("sentinel=%s", repr(sentinel))
        self._consuming = sentinel.consuming_state
        return True

    def _process_queue_item(self, queue_item):
        """Call for each item getting from the queue.

        This should call self.queue.task_done or super()'s."""
        pass


class WorkerPool(object):
    def __init__(self, queue):
        self.worker_queue = queue
        self.log = logging.getLogger(__name__ + '.' +
                                     self.__class__.__name__)

    def add_worker(self, worker):
        self.log.debug("WorkerPool.add_worker worker=%s", worker)
        self.worker_queue.put(worker)
        worker.start()
        self.log.debug("WorkerPool after start()")

    def task_done(self):
        self.log.debug("WorkerPool.task_done")
        self.worker_queue.task_done()

    def join(self):
        self.worker_queue.join()


class TaskQueueConsumer(QueueConsumer):

    def __init__(self, task_queue, worker_pool, result_queue):
        super(TaskQueueConsumer, self).__init__(task_queue)
        self.workers = []
        self.worker_pool = worker_pool
        self.result_queue = result_queue

    def _process_queue_item(self, queue_item):
        """queue_item is a Task object to have a thread created for and run."""

        task = queue_item
        worker = TaskWorkerThread(target=self._target_method,
                                  args=(task.func, task.func_args, task.success_callback, task.error_callback),
                                  name=task.thread_name)
        self.worker_pool.add_worker(worker)

    # Note that the workers we create from Tasks end up adding themselves to the
    # results queue. They populate WorkerPool for thread bookkeeping. ResultsQueueConsumer
    # is responsible for marking result_queue and worker_pool.worker_queue items as task_done().
    def _target_method(self, func, func_args, success_callback, error_callback):
        try:
            retval = func(*func_args)
            self.log.debug("success_callback=%s, retval=%s", success_callback, retval)
            self.result_queue.put_idle((success_callback, retval, None))
        except Exception, e:
            self.log.exception(e)
            self.log.error("busted in target_method func=%s args=%s", func.__name__, func_args)
            self.result_queue.put_idle((error_callback, None, sys.exc_info()))


class ResultQueueConsumer(QueueConsumer):
    """Consumers results, and idle_adds the callback and data to mainloop."""
    def __init__(self, result_queue, worker_pool):
        super(ResultQueueConsumer, self).__init__(result_queue)
        self.worker_pool = worker_pool
        self.result_queue = result_queue

    def _process_queue_item(self, queue_item):
        (callback, retval, error) = queue_item
        self.log.debug("retval=%s", retval)
        self.log.debug("error=%s", error)

        self.worker_pool.task_done()
        # self.worker_pool.task_done() ?

        if not callback:
            return

        ga_GObject.idle_add(callback, retval, error)

# This doesn't currently track active threads, so something could have
# been popped off the task queue, and had one or more threads running, that
# have not yet pushed anything to the result queue. Things could be running
# with both queues empty...
#
# The TasksConsumer could be/is a Workers producer, and ResultsConsumer consumes
#  from WorkersQueue


class Tasks(object):
    def __init__(self):
        self.task_queue = TaskQueue()
        self.worker_pool = WorkerPool(WorkerQueue())
        self.result_queue = ResultQueue()
        self.task_queue_consumer = TaskQueueConsumer(self.task_queue, self.worker_pool, self.result_queue)
        self.result_queue_consumer = ResultQueueConsumer(self.result_queue, self.worker_pool)
        self.log = logging.getLogger(__name__ + '.' +
                                     self.__class__.__name__)

        self._idle_handler_id = None
        self.log.debug("Tasks init")

    def add(self, task):
        """task is a Task. Add to queue and start consuming."""
        self.task_queue.put_idle(task)
        self.log.debug("added task (to become thread=%s)", task.thread_name)

    def idle_handler(self):
        """Idle handler drives the queue consumers."""

        task_queue_consuming = self.task_queue_consumer.consume_one()
        result_queue_consuming = self.result_queue_consumer.consume_one()

        log.debug("task_queue_consuming=%s", task_queue_consuming)
        log.debug("result_queue_consuming=%s", result_queue_consuming)
        log.debug("bool %s", not task_queue_consuming and not result_queue_consuming)
        # If both queues are empty or 'done', return true to unset this handler
        if not task_queue_consuming and not result_queue_consuming:
            self._idle_handler_id = None
            log.debug("Unsetting Tasks.idle_handler")
            return False
        return True

    # TODO: start from AsyncEverything.run or a idle callback version of it
    def run(self):
        # Push a 'start' sentinal into the queue so we don't start empty
        self.task_queue_consumer.start()
        self.result_queue_consumer.start()

        # Add a idle handler to poke at the queue consumers
        self.start_queue_consumers()

    def run_till_empty(self):
        self.run()
        self.stop()

    def stop(self):
        """Queue a QueueStopSentinel to wind down the queue consumers.

        This doesn't stop the QueueConsumers or Tasks directly, but does
        tell the queue Consumers they can stop when their queues are empty.
        Once both queues are empty, self.idle_handler will remove itself."""

        self.task_queue_consumer.stop()
        self.result_queue_consumer.stop()

    def start_queue_consumers(self):
        import traceback
        traceback.print_stack()
        self.log.debug("stack=%s", traceback.format_stack)
        self.log.debug("_idle_handler_id=%s", self._idle_handler_id)
        if not self._idle_handler_id:
            self._idle_handler_id = ga_GObject.idle_add(self.idle_handler)
        self.log.debug("start_queue_consumers, handler_id=%s", self._idle_handler_id)


class AsyncEverything(object):
    """Base class for async handling of tasks.

    You must create this class from the main thread.
    It also requires that the mainloop runs at some point."""

    def __init__(self):
        self.log = logging.getLogger(__name__ + '.' +
                                     self.__class__.__name__)
        self.log.debug("AsyncEverything init")
        self.tasks = Tasks()

    #@main_idle_add
    def _run(self):
        #self.tasks.run()
        self.tasks.run_till_empty()
        return False

    def run(self):
        self.log.debug("run")
        ga_GObject.idle_add(self._run)

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


class AsyncBind(object):

    def __init__(self, certlib):
        self.cp_provider = require(CP_PROVIDER)
        self.identity = require(IDENTITY)
        self.plugin_manager = require(PLUGIN_MANAGER)
        self.certlib = certlib

    # TODO: This should:
    #
    # - run the pre plugin
    # - make the bindByEntitlementPool network request in a async task
    # - if it suceeds, then:
    #     - run it's successcallback in mainthread
    #       -  callvack run post plugin in mainthread
    #       - signal app that it should run (sic) search_button_clicked() to refresh the data in the list
    #         (bind_callback)
    #       - <detangle managerlib.fetch_certificates into events>
    #         (eek, certlib.update etc)
    #       - then (if certlib.update doesnt) signal the app that certs need to be refreshed
    #           (cert_callback)
    # - if it fails,
    #     - error_callback (just show exception/error window).
    #
    # - or - see if registergui.AsyncBacked is close enoug
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
