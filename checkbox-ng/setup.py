#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.

#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

# To avoid an error in atexit._run_exitfuncs while running tests:
import concurrent.futures
import os

from setuptools import setup, find_packages

base_dir = os.path.dirname(__file__)

# Load the README.rst file relative to the setup file
with open(os.path.join(base_dir, "README.rst"), encoding="UTF-8") as stream:
    long_description = stream.read()

# Check if we are running on readthedocs.org builder.
on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

# When building on readthedocs.org, skip all real dependencies as those are
# mocked away in 'plainbox/docs/conf.py'. This speeds up the build process.
# and makes it independent on any packages that are hard to get in a virtualenv
if on_rtd:
    install_requires = []
else:
    install_requires = [
        'plainbox >= 0.3',
        'requests >= 1.0',
    ]

setup(
    name="checkbox-ng",
    version="0.1",
    url="https://launchpad.net/checkbox/",
    packages=find_packages(),
    author="Zygmunt Krynicki",
    test_suite='checkbox_ng.tests.test_suite',
    author_email="zygmunt.krynicki@canonical.com",
    license="GPLv3",
    description="CheckBox / Next Generation",
    long_description=long_description,
    install_requires=install_requires,
    entry_points={
        'console_scripts': [
            'canonical-certification-server=checkbox_ng.main:cert_server',
            'canonical-driver-test-suite-cli=checkbox_ng.main:cdts_cli',
            'checkbox=checkbox_ng.main:main',
            'checkbox-cli=checkbox_ng.main:checkbox_cli',
        ],
        'plainbox.transport': [
            'certification='
            'checkbox_ng.certification:CertificationTransport',
        ],
    },
    include_package_data=True)
