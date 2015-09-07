
# coding=utf8

import re
import time
import logging
import logging.config
import warnings

from functools import partial
from concurrent.futures import Future
from requests import Session

from vk_async.scheduler import Scheduler
from vk_async.logs import LOGGING_CONFIG
from vk_async.utils import *
from vk_async.exceptions import *

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger('vk_async')

VERSION = '0.1'

class API(object):
    LOGIN_URL = 'https://m.vk.com'
    REDIRECT_URI = 'https://oauth.vk_.com/blank.html'
    AUTHORISE_URI = 'https://oauth.vk.com/authorize'
    LOGIN_URI = 'https://m.vk.com/login'
    CAPTCHA_URI = 'https://m.vk.com/captcha.php'

    def __init__(self, access_tokens=None, scope='offline',
                 app_ids=None, user_login='', user_password='',
                 default_timeout=10, api_version='5.28'):

        log_args = dict(access_tokens=access_tokens,
                        scope=scope,
                        default_timeout=default_timeout,
                        api_version=api_version,
                        app_ids=app_ids,
                        user_login=user_login,
                        user_password=user_password)

        logger.debug('API.__init__(access_token=%(access_token)r, '
                     'scope=%(scope)r, default_timeout=%(default_timeout)r, '
                     'api_version=%(api_version)r), app_ids=%(app_ids)r, '
                     'user_login=%(user_login)r, '
                     'user_password=%(user_password)r', log_args)

        self.session = Session()
        self.session.headers['Accept'] = 'application/json'
        self.session.headers['Content-Type'] = 'application/x-www-form-urlencoded'

        self.app_ids = app_ids if app_ids else []
        self.user_login = user_login
        self.user_password = user_password

        self.scope = scope
        self.api_version = api_version

        self.default_timeout = default_timeout
        self.access_tokens = access_tokens
        if not self.access_tokens:
            self.access_tokens = [None] * len(self.app_ids)

        self.schedulers = [Scheduler() for app_id in self.app_ids]
        self.current_scheduler = 0

    def _post_and_process(self, processor, *args, **kwargs):
        """Asynchronously ake HTTP POST query and process result."""
        scheduler = self.schedulers[self.current_scheduler]
        self._next_scheduler()

        def callback(*args, **kwargs):
            return processor(self.session.post(*args, **kwargs))

        return scheduler.call(callback, *args, **kwargs)

    def _next_scheduler(self):
        self.current_scheduler = (self.current_scheduler + 1) % len(self.schedulers)

    def drop_access_token(self, index):
        logger.info('Access token was dropped')
        self.access_tokens[index] = None

    def check_access_token(self, index):
        logger.debug('Check that we have access token')
        if self.access_tokens[index]:
            logger.debug('access_token=%r', self.access_tokens[index])
        else:
            logger.debug('No access token')
            self.get_access_token(index)

    def get_access_token(self, index):
        """
        Get access token using user_login and user_password
        """
        logger.info('Try to get access token via OAuth')

        if self.user_login and not self.user_password:
            # Need user password
            pass

        if not self.user_login and self.user_password:
            # Need user login
            pass

        auth_session = Session()

        logger.debug('GET %s', self.LOGIN_URL)
        login_form_response = auth_session.get(self.LOGIN_URL)
        logger.debug("%s - %s", self.LOGIN_URL, login_form_response.status_code)

        login_form_action = re.findall(r'<form ?.* action="(.+)"',
                                       login_form_response.text)
        if not login_form_action:
            raise VkAuthorizationError('vk_async.com changed login flow')

        # Login
        login_form_data = {
            'email': self.user_login,
            'pass': self.user_password,
        }

        logger.debug('POST %s data %s', login_form_action[0], login_form_data)
        response = auth_session.post(login_form_action[0], login_form_data)
        logger.debug('%s - %s', login_form_action[0], response.status_code)

        logger.debug('Cookies %s', auth_session.cookies)
        logger.info('Login response url %s', response.url)

        captcha = dict()
        if 'remixsid' in auth_session.cookies or 'remixsid6' in auth_session.cookies:
            pass
        elif 'sid=' in response.url:
            self.auth_captcha_is_needed(response, login_form_data)
        elif 'act=authcheck' in response.url:
            self.auth_code_is_needed(response.text, auth_session)
        elif 'security_check' in response.url:
            self.phone_number_is_needed(response.text, auth_session)
        else:
            raise VkAuthorizationError('Authorization error (bad password)')

        # OAuth2
        oauth_data = {
            'response_type': 'token',
            'client_id': self.app_ids[index],
            'scope': self.scope,
            'display': 'mobile',
        }

        logger.debug('POST %s data %s', self.AUTHORISE_URI, oauth_data)
        response = auth_session.post(self.AUTHORISE_URI, oauth_data)
        logger.debug('%s - %s', self.AUTHORISE_URI, response.status_code)
        logger.info('OAuth URL: %s %s', response.request.url, oauth_data)

        if 'access_token' not in response.url:
            logger.info('Geting permissions')
            form_action = re.findall(r'<form method="post" action="(.+?)">', response.text)
            logger.debug('form_action %s', form_action)
            if form_action:
                response = auth_session.get(form_action[0])
            else:
                try:
                    json_data = response.json()
                except ValueError:  # not json in response
                    error_message = 'OAuth2 grant access error'
                else:
                    error_message = 'VK error: [{0}] {1}'.format(
                        json_data['error'],
                        json_data['error_description']
                    )
                auth_session.close()
                raise VkAuthorizationError(error_message)
            logger.info('Permissions obtained')

        auth_session.close()

        parsed_url = urlparse(response.url)
        logger.debug('Parsed URL: %s', parsed_url)

        token_dict = dict(parse_qsl(parsed_url.fragment))
        if 'access_token' in token_dict:
            self.access_tokens[index] = token_dict['access_token']
            self.access_token_expires_in = token_dict['expires_in']
            logger.info('Success! expires_in: %s\ntoken: %s', self.access_token_expires_in, self.access_tokens[index])
            return self.access_token, self.access_token_expires_in
        else:
            raise VkAuthorizationError('OAuth2 authorization error')

    def __getattr__(self, method_name):
        return APIMethod(self, method_name)

    def _process_response(self, scheduler, method_name,
                          method_kwargs, response):

        response.raise_for_status()
        # there are may be 2 dicts in 1 json
        # for example: {'error': ...}{'response': ...}
        errors = []
        error_codes = []
        for data in json_iter_parse(response.text):
            if 'error' in data:
                error_data = data['error']
                if error_data['error_code'] == CAPTCHA_IS_NEEDED:
                    return self.captcha_is_needed(error_data, method_name,
                                                  **method_kwargs)

                error_codes.append(error_data['error_code'])
                errors.append(error_data)

            if 'response' in data:
                for error in errors:
                    warnings.warn(str(error))
                return data['response']

        if AUTHORIZATION_FAILED in error_codes:  # invalid access token
            logger.info('Authorization failed. Access token will be dropped')
            self.drop_access_token(scheduler)
            return self(method_name, **method_kwargs)
        else:
            raise VkAPIMethodError(errors[0])

    def __call__(self, method_name, **method_kwargs):
        self.check_access_token(self.current_scheduler)
        processor = partial(self._process_response, self.current_scheduler,
                            method_name, method_kwargs)


        return self.method_request(method_name, processor, **method_kwargs)


    def method_request(self, method_name, processor,
                       timeout=None, **method_kwargs):
        params = {
            'timestamp': int(time.time()),
            'v': self.api_version,
        }
        if self.access_token:
            params['access_token'] = self.access_tokens[self.current_scheduler]

        method_kwargs = stringify_values(method_kwargs)
        params.update(method_kwargs)
        url = 'https://api.vk.com/method/' + method_name

        logger.info('Make request %s, %s', url, params)

        return self._post_and_process(processor, url, params,
                                      timeout=timeout or self.default_timeout)

    def captcha_is_needed(self, error_data, method_name, **method_kwargs):
        raise VkAPIMethodError(error_data)
    
    def auth_code_is_needed(self, content, session):
        raise VkAuthorizationError('Authorization error (2-factor code is needed)')
    
    def auth_captcha_is_needed(self, content, session):
        raise VkAuthorizationError('Authorization error (captcha)')
    
    def phone_number_is_needed(self, content, session):
        raise VkAuthorizationError('Authorization error (phone number is needed)')
    

class APIMethod(object):
    __slots__ = ['_api_session', '_method_name']

    def __init__(self, api_session, method_name):
        self._api_session = api_session
        self._method_name = method_name

    def __getattr__(self, method_name):
        return APIMethod(self._api_session, self._method_name + '.' + method_name)

    def __call__(self, **method_kwargs):
        return self._api_session(self._method_name, **method_kwargs)
