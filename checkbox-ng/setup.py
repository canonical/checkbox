#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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

import sys
import os

from setuptools import setup, find_packages

if "test" in sys.argv:
    # Reset locale for setup.py test
    os.environ["LANG"] = ""
    os.environ["LANGUAGE"] = ""
    os.environ["LC_ALL"] = "C.UTF-8"

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
        'lxml >= 2.3',
    ]

setup(
    name="plainbox",
    version="0.7.dev",
    url="https://launchpad.net/plainbox/",
    packages=find_packages(),
    author="Zygmunt Krynicki",
    test_suite='plainbox.tests.test_suite',
    author_email="zygmunt.krynicki@canonical.com",
    license="GPLv3",
    description="Simple replacement for checkbox",
    long_description=long_description,
    install_requires=install_requires,
    extras_require={
        'XLSX': 'XlsxWriter >= 0.3',
    },
    entry_points={
        'console_scripts': [
            'plainbox=plainbox.public:main',
            ('plainbox-trusted-launcher-1='
             'plainbox.impl.secure.launcher1:main'),
        ],
        'plainbox.exporter': [
            'text=plainbox.impl.exporter.text:TextSessionStateExporter',
            'json=plainbox.impl.exporter.json:JSONSessionStateExporter',
            'rfc822=plainbox.impl.exporter.rfc822:RFC822SessionStateExporter',
            'xlsx=plainbox.impl.exporter.xlsx:XLSXSessionStateExporter [XLSX]',
            'xml=plainbox.impl.exporter.xml:XMLSessionStateExporter',
            'html=plainbox.impl.exporter.html:HTMLSessionStateExporter',
        ],
        'plainbox.buildsystem': [
            'make=plainbox.impl.buildsystems:MakefileBuildSystem',
            'go=plainbox.impl.buildsystems:GoBuildSystem',
            'autotools=plainbox.impl.buildsystems:AutotoolsBuildSystem',
        ],
        'plainbox.unit': [
            'unit=plainbox.impl.unit:Unit',
            'job=plainbox.impl.unit.job:JobDefinition',
        ],
    },
    include_package_data=True)
