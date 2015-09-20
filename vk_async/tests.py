# Copyright 2015 Artur Chakhvadze <nopadon@yandex.ru>
# Copyright 2014-2015 Dmitry Voronin <dimka665@gmail.com>.
# All Rights Reserved.

"""Tests."""

__author__ = 'Artur Chakhvadze (norpadon@yandex.ru)'

import os
import sys
import time

import unittest
import vk_async.fetcher
from tornado.ioloop import IOLoop
from tornado import gen

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# copy to test_props.py and fill it
APP_IDS = []  # aka API/Client id

USER_LOGIN = ''  # user email or phone number
USER_PASSWORD = ''

from test_props import APP_IDS, USER_LOGIN, USER_PASSWORD


class VkAsyncTestCase(unittest.TestCase):
    def setUp(self):
        self.app = vk_async.fetcher.Fetcher(
            app_ids=APP_IDS,
            username=USER_LOGIN,
            password=USER_PASSWORD
        )

    @gen.coroutine
    def get_users(self):
        users = yield [self.app.execute.getUserData(user_id=uid) for uid in [1, 2, 3]]
        print(*users, sep='\n')

    def test_init(self):
        IOLoop.current().run_sync(self.get_users)

if __name__ == '__main__':
    unittest.main()

