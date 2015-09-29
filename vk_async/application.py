# Copyright 2015 Artur Chakhvadze <nopadon@yandex.ru>.
# Copyright 2014-2015 Dmitry Voronin <dimka665@gmail.com>.
# All Rights Reserved.

"""Basic VK API wrapper."""

__author__ = 'Artur Chakhvadze (norpadon@yandex.ru)'

import time
from collections import deque
from datetime import datetime, timedelta
from tornado import gen
from tornado.ioloop import IOLoop
from tornado.locks import Lock
from tornado.httputil import HTTPHeaders
from tornado.httpclient import AsyncHTTPClient, HTTPRequest, HTTPError

from httpclient_session import Session
from httpclient_session.cookies import extract_cookies_to_jar

from vk_async.utils import *
from vk_async.exceptions import *


class Application(object):
    """Wrapper around single vk application."""

    LOGIN_URL = 'https://m.vk.com'
    AUTHORIZE_URL = 'https://oauth.vk.com/authorize'
    CAPTCHA_URI = 'https://m.vk.com/captcha.php'
    API_URL = 'https://api.vk.com/method/'

    SCOPE = 'offline'

    DEFAULT_HEADERS = HTTPHeaders({
        'accept': 'application/json',
        'accept-charset': 'utf-8',
        'content-type': 'application/x-www-form-urlencoded',
    })

    def __init__(self, app_id, username, password, max_requests_per_second=3,
                 default_timeout=20, api_version='5.28'):
        """Create new application object

        Args:
            app_id: id of VK application.
            username: user's phone number or email.
            password: user's password.
            max_requests_per_second: maximum number of requests that
                application can send per one second.
                Depends on number of users. Default value is 3.
            default_timeout: default timeout for ip requests.
            api_version: version of VK API used.
        """
        self.last_requests = deque([datetime.min] * max_requests_per_second)
        self.max_requests_per_second = max_requests_per_second

        self.app_id = app_id
        self.username = username
        self.password = password

        self.api_version = api_version

        self.default_timeout = default_timeout

        self.client_session = Session(AsyncHTTPClient)
        self.queue_lock = Lock()

        IOLoop.current().run_sync(self.get_access_token)

    @gen.coroutine
    def _post(self, url, params, handle_redirects=True):
        """Make HTTP post request, handle redirects and timeouts.

        Args:
            url: url to make request.
            params: request parameters.
            handle_redirects: process redirects manually
                (use to handle cookies properly).
        """
        request = HTTPRequest(
            url,
            method='POST',
            headers=self.DEFAULT_HEADERS.copy(),
            follow_redirects=not handle_redirects,
            request_timeout=self.default_timeout,
            body=urlencode(params),
        )

        # Handle timeouts.
        while True:
            try:
                # If no redirect.
                response = yield self.client_session.fetch(request)
                return response
            except HTTPError as e:
                # If timeout happened just retry.
                if e.code == 599:
                    continue
                # Else it is redirect.
                response = e.response
                break

        # If access token has been acquired.
        if response.code == 405:
            return response

        # Handle redirect.
        new_url = response.headers['Location']
        if new_url == '/':
            new_url = self.LOGIN_URL
        # Save cookies.
        extract_cookies_to_jar(self.client_session.cookies, request, response)

        response = yield self._post(new_url, params, handle_redirects)
        return response

    def __getattr__(self, method_name):
        return APIMethod(self, method_name)

    @gen.coroutine
    def __call__(self, method_name, **method_kwargs):
        response = yield self.method_request(method_name, **method_kwargs)

        # There may be 2 dicts in one JSON.
        # For example: {'error': ...}{'response': ...}.
        errors = []
        error_codes = []
        for data in json_iter_parse(response.body.decode('utf-8')):
            if 'error' in data:
                error_data = data['error']
                error_codes.append(error_data['error_code'])
                errors.append(error_data)

            if 'response' in data:
                for error in errors:
                    logger.warning(str(error))

                return data['response']

        # Handle "Too many requests" error.
        if TO_MANY_REQUESTS in error_codes:
            return (yield self(method_name, **method_kwargs))

        raise VkAPIMethodError(errors[0])

    @gen.coroutine
    def method_request(self, method_name, **method_kwargs):
        """Make call to VK API.

        Args:
            method_name: name of VK API method.
            **method_args: arguments to VK API method.
        """
        # Wait if too many requests were made.
        with (yield self.queue_lock.acquire()):
            first_request = self.last_requests.pop()
            now = datetime.now()
            delay = max(0, 1.1 - (now - first_request).total_seconds())
            yield gen.sleep(delay)

            params = {
                'timestamp': int(time.time()),
                'access_token': self.access_token,
                'v': self.api_version,
            }

            method_kwargs = stringify_values(method_kwargs)
            params.update(method_kwargs)
            url = self.API_URL + method_name

            result = yield self._post(url, params)
            self.last_requests.appendleft(datetime.now())

        return result

    @gen.coroutine
    def get_access_token(self):
        """Get access token using app id and user login and password."""
        # Log in and get cookies.
        yield self.login()
        # Authorize via OAuth2.
        auth_response_url_query = yield self.oauth2_authorization()

        if 'access_token' in auth_response_url_query:
            self.access_token = auth_response_url_query['access_token']
        else:
            raise VkAuthError('OAuth2 authorization error')

    @gen.coroutine
    def login(self, login_form_action=None):
        """Log in and set cookies.

        Args:
            login_form_action: url of login action.
                Default is retrieved from m.vk.api/login.
        """
        if login_form_action is None:
            response = yield self.client_session.fetch(self.LOGIN_URL)
            login_form_action = get_form_action(response.body.decode('utf-8'))
            if not login_form_action:
                raise VkAuthError('VK changed login flow')

        login_form_data = {
            'email': self.username,
            'pass': self.password,
        }

        response = yield self._post(
            login_form_action,
            login_form_data,
        )

        # Check for session id.
        if ('remixsid' in self.client_session.cookies or
                'remixsid6' in self.client_session.cookies):
            return response

        raise VkAuthError('Authorization error (incorrect password)')

    @gen.coroutine
    def oauth2_authorization(self):
        """OAuth2 procedure for getting access token."""
        auth_data = {
            'client_id': self.app_id,
            'display': 'mobile',
            'response_type': 'token',
            'scope': self.SCOPE,
            'v': self.api_version,
        }

        response = yield self._post(
            self.AUTHORIZE_URL,
            auth_data,
        )

        response_url_query = get_url_query(response.effective_url)
        if 'access_token' in response_url_query:
            return response_url_query

        # Permissions is needed
        response_body = response.body.decode('utf-8')
        form_action = get_form_action(response_body)
        if form_action:
            response = yield self._post(form_action, {})
            response_url_query = get_url_query(response.effective_url)
            return response_url_query

        try:
            response_json = json.loads(response_body)
        except ValueError:  # not JSON in response
            error_message = 'OAuth2 grant access error'
        else:
            error_message = 'VK error: [{}] {}'.format(
                response_json['error'],
                response_json['error_description']
            )
        raise VkAuthError(error_message)


class APIMethod(object):
    """Wrapper around VK API method call."""
    __slots__ = ['_api_session', '_method_name']

    def __init__(self, api_session, method_name):
        self._api_session = api_session
        self._method_name = method_name

    def __getattr__(self, method_name):
        logger.debug('Create API Method')
        return APIMethod(
            self._api_session,
            self._method_name + '.' + method_name,
        )

    @gen.coroutine
    def __call__(self, **method_kwargs):
        return (yield self._api_session(self._method_name, **method_kwargs))

