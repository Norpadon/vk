
#!/usr/bin/env python

import os
import re
from setuptools import setup, find_packages

setup(
    name='vk_async',
    version='1.0',

    author='Artur Chakhvadze',
    author_email='norpadon@yandex.com',

    url='https://github.com/norpadon/vk_async',
    description='vk.com API Python wrapper',

    packages=find_packages(),
    install_requires=[
        'tornado'
    ],

    license='MIT License',
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    keywords='vk.com async api vk wrappper',
)
