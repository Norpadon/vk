
# coding=utf8

import os
import sys
import time

import unittest
import vk_async

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# copy to test_props.py and fill it
APP_IDS = []  # aka API/Client id

USER_LOGIN = ''  # user email or phone number
USER_PASSWORD = ''

from test_props import APP_IDS, USER_LOGIN, USER_PASSWORD


class VkAsyncTestCase(unittest.TestCase):

    def setUp(self):
        self.vk_api = vk_async.API(app_ids=APP_IDS,
                                   user_login=USER_LOGIN,
                                   user_password=USER_PASSWORD)

    def test_get_server_time(self):
        time_1 = time.time() - 1
        time_2 = time_1 + 10
        server_time = self.vk_api.getServerTime().result()
        self.assertTrue(time_1 <= server_time <= time_2)

    def test_get_profiles_via_token(self):
        profiles = self.vk_api.users.get(user_id=1).result()
        self.assertEqual(profiles[0]['last_name'], u'Дуров')

    def test_get_friends(self):
        friends = self.vk_api.friends.get(user_id=1)
        self.assertEqual(friends.fmap(lambda fs: len(fs) > 0).result(), True)

    def test_error(self):
        def func():
            def err(elem):
                raise Exception(":C")

            return self.vk_api.friends.get(user_id=1).fmap(err).result()

        self.assertRaises(Exception, func)

if __name__ == '__main__':
    unittest.main()

