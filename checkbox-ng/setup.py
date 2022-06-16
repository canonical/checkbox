#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2018 Canonical Ltd.
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

import concurrent.futures
import os
import sys

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
        'requests >= 1.0',
        'urwid >= 1.1.1',
        'Jinja2 >= 2.7',
        'xlsxwriter',
    ]

setup(
    name="checkbox-ng",
    version="1.18.0rc1",
    url="https://launchpad.net/checkbox-ng/",
    packages=find_packages(),
    author="Zygmunt Krynicki",
    test_suite='checkbox_ng.tests.test_suite',
    author_email="zygmunt.krynicki@canonical.com",
    license="GPLv3",
    platforms=["POSIX"],
    description="Checkbox - Command Line Test Runner",
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
        'Programming Language :: Python :: 3.4',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Software Development :: Testing',
        'Topic :: System :: Benchmark',
        'Topic :: Utilities',
    ],
    install_requires=install_requires,
    entry_points={
        'console_scripts': [
            'checkbox-cli=checkbox_ng.launcher.checkbox_cli:main',
            'checkbox-provider-tools=checkbox_ng.launcher.provider_tools:main',
        ],
        'plainbox.exporter': [
            'text=plainbox.impl.exporter.text:TextSessionStateExporter',
            'tar=plainbox.impl.exporter.tar:TARSessionStateExporter',
            'xlsx=plainbox.impl.exporter.xlsx:XLSXSessionStateExporter',
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
            'pxu-override=plainbox.impl.xparsers:FieldOverride.parse',
        ],
        'plainbox.transport': [
            'file=plainbox.impl.transport:FileTransport',
            'stream=plainbox.impl.transport:StreamTransport',
            'submission-service='
            'checkbox_ng.certification:SubmissionServiceTransport',
        ],
    },
    include_package_data=True)
