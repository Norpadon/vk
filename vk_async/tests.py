
# coding=utf8

import os
import sys
import time

import unittest
import vk_async

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# copy to test_props.py and fill it
APP_ID = ''  # aka API/Client id

USER_LOGIN = ''  # user email or phone number
USER_PASSWORD = ''

from test_props import APP_IDS, USER_LOGIN, USER_PASSWORD


class VkTestCase(unittest.TestCase):

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
        del self.vk_api.schedulers[0]

if __name__ == '__main__':
    unittest.main()
