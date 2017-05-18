# -*- coding: utf-8 -*-


import re
import os

from setuptools import setup


DIR = os.path.dirname(__file__)


with open(os.path.join(DIR, 'ipc', '__init__.py')) as f:
    version = re.search(r'__version__\s+=\s+[\'\"]+(.*)[\'\"]+', f.read()).group(1)


setup(
    name='ipc',
    version=version,
    packages=['ipc'],
    description='Interprocess communication via standard streams.',
    zip_safe=False,
    platforms='any',
    long_description=open(os.path.join(DIR, 'README.rst')).read(),
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
