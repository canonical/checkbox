#!/usr/bin/env bash
#
# This file is part of Checkbox.
#
# Copyright 2022 Canonical Ltd.
#
# Authors: Maciej Kisielewski <maciej.kisielewski@canonical.com>
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

# All the sudirectories here contain sources for snaps for different series.
# Those snaps have files in common, those files are placed in common_series_uc
# This tool copies over those files to the snap's directory so it can be
# snapped.

series=$1

if [ -z "$series" ]; then
	echo "usage: $0 SERIES"
	echo
	echo "This tool populates snap's directory with missing files that are"
	echo "common between all series. The files in question may be found in"
	echo "the common_series_uc directory"
	exit 1
fi

if [ ! -d "$series" ]; then
	echo "$series not found"
	exit 1
fi

echo "Copying over common_series_uc/* to $series"
rsync -r --links common_series_uc/ $series/
echo "Dumping version in version file for $series..."
if python3 -c 'import setuptools_scm' &> /dev/null; then
	# setuptools_scm fetches the version calculating it from the latest tag.
	# We use the default setuptools_scm schema refert to:
	# https://pypi.org/project/setuptools-scm/ for more infos. Generally:
	# no distance and clean: {tag}
	# distance and clean: {next_version}.dev{distance}+{scm letter}{revision hash}
	# no distance and not clean: {tag}+dYYYYMMDD
	# distance and not clean: {next_version}.dev{distance}+{scm letter}{revision hash}.dYYYYMMDD
	(cd .. && python3 -m setuptools_scm | grep -oP "\S+$") 2>/dev/null 1>$series/version.txt
else
	echo "Error: Python package 'setuptools-scm' not available."
	echo "Please install it and try again."
	exit 1
fi
