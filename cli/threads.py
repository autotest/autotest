#
# Copyright 2008 Google Inc.
# Released under the GPLv2

import threading, Queue

class ThreadPool:
    """ A generic threading class for use in the CLI
    ThreadPool class takes the function to be executed as an argument and
    optionally number of threads.  It then creates multiple threads for
    faster execution. """

    def __init__(self, function, numthreads=40):
        assert(numthreads > 0)
        self.threads = Queue.Queue(0)
        self.function = function
        self.numthreads = 0
        self.queue = Queue.Queue(0)
        self._start_threads(numthreads)


    def wait(self):
        """ Checks to see if any threads are still working and
            blocks until worker threads all complete. """
        for x in xrange(self.numthreads):
            self.queue.put('die')
        # As only spawned threads are allowed to add new ones,
        # we can safely wait for the thread queue to be empty
        # (if we're at the last thread and it creates a new one,
        # it will get queued before it finishes).
        dead = 0
        while True:
            try:
                thread = self.threads.get(block=True, timeout=1)
                if thread.isAlive():
                    thread.join()
                dead += 1
            except Queue.Empty:
                assert(dead == self.numthreads)
                return


    def queue_work(self, data):
        """ Takes a list of items and appends them to the
            work queue. """
        [self.queue.put(item) for item in data]


    def add_one_thread_post_wait(self):
        # Only a spawned thread (not the main one)
        # should call this (see wait() for details)
        self._start_threads(1)
        self.queue.put('die')


    def _start_threads(self, nthreads):
        """ Start up threads to spawn workers. """
        self.numthreads += nthreads
        for i in range(nthreads):
            thread = threading.Thread(target=self._new_worker)
            thread.setDaemon(True)
            self.threads.put(thread)
            thread.start()


    def _new_worker(self):
        """ Spawned worker threads. These threads loop until queue is empty."""
        while True:
            # Blocking call
            data = self.queue.get()
            if data == 'die':
                return
            try:
                self.function(data)
            except Exception:
                # We don't want one function that raises to kill everything.
                # TODO: Maybe keep a list of errors or something?
                pass
