
from time import sleep
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Thread
from collections import deque
from requests import Session
from datetime import datetime, timedelta
from functools import partial

class Scheduler(object):
    """Scheduler provides async interface for making VK API calls and
    incapsulates time management for queries.
    """

    def __init__(self, max_requests_per_second=3):
        self.last_requests = deque([datetime.min] * max_requests_per_second)
        self.max_requests_per_second = max_requests_per_second
        self.executor = ThreadPoolExecutor(max_workers=1)

    def _wait_and_execute(self, callback):
        first_request = self.last_requests.pop()
        now = datetime.now()
        delay = max(0, 1 - (now - first_request).total_seconds())
        sleep(delay)
        self.last_requests.appendleft(now)
        return callback()

    def __del__(self):
        self.executor.shutdown()

    def call(self, fn, *args, **kwargs):
        callback = partial(fn, *args, **kwargs)
        result = self.executor.submit(self._wait_and_execute, callback)
        return FutureFunctor.wrap(result, self.executor)


class FutureFunctor(Future):
    @staticmethod
    def wrap(future, executor):
        future.__class__ = FutureFunctor
        future.executor = executor
        return future

    @staticmethod
    def lift(value, executor=None):
        result = FutureFunctor(executor)
        result.set_result(value)
        return result

    def __init__(self, executor):
        self.executor = executor
        Future.__init__(self)

    def fmap(self, func, timeout=None):
        def callback():
            return func(self.result(timeout))

        if self.executor:
            result = self.executor.submit(callback)
            return FutureFunctor.wrap(result, self.executor)
        else:
            return FutureFunctor.lift(callback())

