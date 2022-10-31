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
# Those snaps have files in common, those files are placed in common_files.
# This tool copies over those files to the snap's directory so it can be
# snapped.

series=$1

if [ -z "$series" ]; then
	echo "usage: $0 SERIES"
	echo
	echo "This tool populates snap's directory with missing files that are"
	echo "common between all series. The files in question may be found in"
	echo "the common_files directory"
	exit 1
fi

if [ ! -d "$series" ]; then
	echo "$series not found"
	exit 1
fi

echo "Copying over common_files/* to $series"
rsync -r --links common_files/ $series/
echo "Copying over providers to $series"
rsync -r --links ../providers $series/
echo "Copying over checkbox-ng to $series"
rsync -r --links ../checkbox-ng $series/
echo "Copying over checkbox-support to $series"
rsync -r --links ../checkbox-support $series
