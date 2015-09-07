import sys


LOGGING_CONFIG = {
    'version': 1,
    'loggers': {
        'vk_async': {
            'level': 'INFO',
            'handlers': ['vk_async-stdout'],
            'propagate': False,
            },
        },
    'handlers': {
        'vk_async-stdout': {
            'class': 'logging.StreamHandler',
            'stream': sys.stdout,
            'formatter': 'vk_async-verbose',
        },
    },
    'formatters': {
        'vk_async-verbose': {
            'format': '%(asctime)s %(name) -14s %(levelname)s: %(message)s',
        },
    },
}

