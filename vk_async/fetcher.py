# Copyright 2015 Artur Chakhvadze <nopadon@yandex.ru>
# All Rights Reserved.

"""Classes for making extensive parallel requests from set of applications."""

__author__ = 'Artur Chakhvadze (norpadon@yandex.ru)'

from vk_async.application import Application, APIMethod
from tornado import gen


class Fetcher(object):
    """Fetcher provides single interface for set of VK Applications
    and incapsulates queuing.
    """

    def __init__(self, app_ids, username, password, **kwargs):
        """Create new fetcher.

        Args:
            app_ids: list of application ids.
            username: user's email or phone number.
            password: user's password.
            **kwargs: arguments to pass to each Application instance
        """
        self.applications = [
            Application(app_id, username, password, **kwargs)
            for app_id in app_ids
        ]

        self.current_application = 0

    @gen.coroutine
    def __call__(self, method_name, **method_kwargs):
        application = self.applications[self.current_application]
        self.current_application += 1
        return (yield application(method_name, **method_kwargs))

    def __getattr__(self, method_name):
        return APIMethod(self, method_name)
