#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2012-2015 Canonical Ltd.
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
from distutils.version import LooseVersion

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

# Check if we're able to include OAuth support
try:
    import requests
except ImportError:
    extra_install_requires = ['requests >= 1.0']
else:
    if LooseVersion(requests.__version__) >= LooseVersion('2.0.0'):
        extra_install_requires = ['requests >= 2.0.0', 'requests-oauthlib']
    else:
        extra_install_requires = ['requests >= 1.0']

setup(
    name="plainbox",
    version="0.26c1",
    url="https://launchpad.net/plainbox/",
    packages=find_packages(),
    author="Zygmunt Krynicki",
    test_suite='plainbox.tests.test_suite',
    author_email="zygmunt.krynicki@canonical.com",
    license="GPLv3",
    platforms=["POSIX"],
    description="Toolkit for software and hardware integration testing",
    long_description=long_description,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Environment :: Console :: Curses',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Manufacturing',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Natural Language :: Polish',
        'Operating System :: POSIX',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Software Development :: Testing',
        'Topic :: System :: Benchmark',
        'Topic :: Utilities',
    ],
    install_requires=[
        'Jinja2 >= 2.7',
        'guacamole >= 0.9',
        'padme >= 1.1.1',
    ] + extra_install_requires,
    extras_require={
        'XLSX': 'XlsxWriter >= 0.3',
    },
    entry_points={
        'console_scripts': [
            'plainbox=plainbox.public:main',
            'stubbox=plainbox.impl.box:stubbox_main',
            ('plainbox-trusted-launcher-1='
             'plainbox.impl.secure.launcher1:main'),
            'plainbox-qml-shell=plainbox.qml_shell.qml_shell:main',
        ],
        'plainbox.exporter': [
            'text=plainbox.impl.exporter.text:TextSessionStateExporter',
            'json=plainbox.impl.exporter.json:JSONSessionStateExporter',
            'rfc822=plainbox.impl.exporter.rfc822:RFC822SessionStateExporter',
            'xlsx=plainbox.impl.exporter.xlsx:XLSXSessionStateExporter [XLSX]',
            'jinja2=plainbox.impl.exporter.jinja2:Jinja2SessionStateExporter',
        ],
        'plainbox.buildsystem': [
            'make=plainbox.impl.buildsystems:MakefileBuildSystem',
            'go=plainbox.impl.buildsystems:GoBuildSystem',
            'autotools=plainbox.impl.buildsystems:AutotoolsBuildSystem',
        ],
        'plainbox.unit': [
            'unit=plainbox.impl.unit.unit:Unit',
            'job=plainbox.impl.unit.job:JobDefinition',
            'template=plainbox.impl.unit.template:TemplateUnit',
            'category=plainbox.impl.unit.category:CategoryUnit',
            'test plan=plainbox.impl.unit.testplan:TestPlanUnit',
            'manifest entry=plainbox.impl.unit.manifest:ManifestEntryUnit',
            ('packaging meta-data='
             'plainbox.impl.unit.packaging:PackagingMetaDataUnit'),
            'exporter=plainbox.impl.unit.exporter:ExporterUnit',
        ],
        'plainbox.parsers': [
            'pxu=plainbox.impl.secure.rfc822:load_rfc822_records',
            'regex=plainbox.impl.xparsers:Re.parse',
            'whitelist=plainbox.impl.xparsers:WhiteList.parse',
            'pxu-override=plainbox.impl.xparsers:FieldOverride.parse',
        ],
        'plainbox.transport': [
            'file=plainbox.impl.transport:FileTransport',
            'stream=plainbox.impl.transport:StreamTransport',
        ],
    },
    include_package_data=True)
