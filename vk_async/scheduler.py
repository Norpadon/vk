
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
        self.kill()

    def kill(self):
        self.queue = None

    def call(self, fn, *args, **kwargs):
        callback = partial(fn, *args, **kwargs)
        return self.executor.submit(self._wait_and_execute, callback)
