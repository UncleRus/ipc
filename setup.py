# -*- coding: utf-8 -*-

# IPC: A python library for interprocess communication via standard streams.
#
# $Id$
#
# License: MIT
# Copyright 2015-2017 Ruslan V. Uss (https://github.com/UncleRus)
# Copyright 2017 Oleg Golovanov (https://github.com/oleg-golovanov)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.


import re
import os

from setuptools import setup


DIR = os.path.dirname(__file__)


with open(os.path.join(DIR, 'ipc.py')) as f:
    version = re.search(r'__version__\s+=\s+[\'\"]+(.*)[\'\"]+', f.read()).group(1)


setup(
    name='ipc',
    version=version,
    py_modules=['ipc'],
    data_files=[('', ['LICENSE', 'README.md'])],
    description='Interprocess communication via standard streams.',
    zip_safe=False,
    platforms='any',
    long_description=open(os.path.join(DIR, 'README.md')).read(),
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.0',
        'Programming Language :: Python :: 3.1',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
