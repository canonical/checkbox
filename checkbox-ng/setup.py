#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.


from setuptools import setup, find_packages


setup(
    name="plainbox",
    version="0.2",
    url="https://launchpad.net/checkbox/",
    packages=find_packages(),
    author="Zygmunt Krynicki",
    test_suite='plainbox.tests.test_suite',
    author_email="zygmunt.krynicki@canonical.com",
    license="GPLv3+",
    description="Simple replacement for checkbox",
    long_description=open("README.rst", "rt", encoding="UTF-8").read(),
    tests_require=[
        'mock',
    ],
    install_requires=[
        'lxml >= 2.3',
        'requests >= 1.0',
    ],
    data_files=[
        ("share/polkit-1/actions",
            ["plainbox/data/org.freedesktop.policykit.pkexec.policy"])
    ],
    entry_points={
        'console_scripts': [
            'plainbox=plainbox.public:main',
            'checkbox-trusted-launcher='
            'plainbox.impl.secure.checkbox_trusted_launcher:main',
        ],
        'plainbox.exporter': [
            'text=plainbox.impl.exporter.text:TextSessionStateExporter',
            'json=plainbox.impl.exporter.json:JSONSessionStateExporter',
            'rfc822=plainbox.impl.exporter.rfc822:RFC822SessionStateExporter',
            'xml=plainbox.impl.exporter.xml:XMLSessionStateExporter',
        ],
        'plainbox.transport': [
            'certification='
            'plainbox.impl.transport.certification:CertificationTransport',
        ],
    },
    include_package_data=True)
