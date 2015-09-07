
from time import sleep
from concurrent.futures import Future
from threading import Thread
from collections import deque
from requests import Session
from datetime import datetime, timedelta
from functools import partial

SLEEP_INTERVAL = 0.1

class Scheduler(object):
    """Scheduler provides async interface for making VK API calls and
    incapsulates time management for queries.
    """

    def __init__(self, max_requests_per_second=3):
        self.session = Session()
        self.session.headers['Accept'] = 'application/json'
        self.session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        self.last_requests = deque([datetime.min] * max_requests_per_second)
        self.queue = deque()
        self.max_requests_per_second = max_requests_per_second

    def _kick_scheduler(self):
        self.executor = Thread(None, self._init_scheduler)
        self.executor.start()

    def _init_scheduler(self):
        while self.queue:
            task, future = self.queue.pop()
            first_request = self.last_requests.pop()
            now = datetime.now()
            delay = max(0, 1 - (now - first_request).total_seconds())
            self.last_requests.appendleft(now + timedelta(seconds=delay))
            sleep(delay)
            try:
                future.set_result(task())
            except Exception as e:
                future.set_exception(e)
        self.executor = None

    def _add_task(self, func):
        future = Future()
        self.queue.appendleft((func, future))
        return future

    def __del__(self):
        self.kill()
        if self.executor:
            self.executor.join()

    def kill(self):
        self.queue = None

    def call(self, *args, **kwargs):
        callback = partial(self.session.post, *args, **kwargs)
        result = self._add_task(callback)
        if not self.executor:
            self._kick_scheduler()

        return result

