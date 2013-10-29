#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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
    name="checkbox-ng",
    version="0.1",
    url="https://launchpad.net/checkbox/",
    packages=find_packages(),
    author="Zygmunt Krynicki",
    test_suite='checkbox_ng.tests.test_suite',
    author_email="zygmunt.krynicki@canonical.com",
    license="GPLv3+",
    description="CheckBox / Next Generation",
    long_description=open("README.rst", "rt", encoding="UTF-8").read(),
    install_requires=[
        'plainbox >= 0.3',
    ],
    entry_points={
        'console_scripts': [
            'checkbox=checkbox_ng.main:main',
            'canonical-certification-server=checkbox_ng.main:cert_server',
        ],
    },
    include_package_data=True)
