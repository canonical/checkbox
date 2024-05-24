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
# Those snaps have files in common, those files are placed in
# common_series_classic.  This tool copies over those files to the snap's
# directory so it can be snapped.

series=$1

if [ -z "$series" ]; then
	echo "usage: $0 SERIES"
	echo
	echo "This tool populates snap's directory with missing files that are"
	echo "common between all series. The files in question may be found in"
	echo "the common_series_classic directory"
	exit 1
fi

if [ ! -d "$series" ]; then
	echo "$series not found"
	exit 1
fi

echo "Copying over common_series_classic/* to $series"
rsync -r --links common_series_classic/ ..
echo "Copying over snapcraft.yaml"
rsync -r --links $series ..
echo "Dumping version in version file for $series..."
if which python3 1>/dev/null && which git 1>/dev/null; then
	# get_version.py produces a version number from the traceability
	# markers in the history of the repository in the form
	# vX.Y.Z-devXX, where XX is the number of commits since the latest tag
	(cd .. && python3 tools/release/get_version.py -v --dev-suffix --output-format snap) 1>../version.txt
else
	echo "Error: python3 and git binaries are required."
	echo "Please install them and try again."
	echo "If they are not installed run: "
	echo "  apt install python3 git"
	exit 1
fi
rm ../.gitignore
