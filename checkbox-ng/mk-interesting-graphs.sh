#!/bin/sh
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

# Create a few interesting graphs

# set -x  # it takes a moment, let's keep users busy
mkdir -p graphs
# Find some jobs from each main category
# The grep / discards stuff that does not have category/name pattern
# The rest just gets the category string
for pattern in $(plainbox dev special --list-jobs | grep '/' | cut -d '/' -f 1 | sort | uniq); do
    plainbox dev special -i $pattern'.*' --dot | dot -Tsvg -o graphs/$pattern.svg
    plainbox dev special -i $pattern'.*' --dot --dot-resources | dot -Tsvg -o graphs/$pattern-with-resources.svg
done
plainbox dev special --dot | dot -Tsvg -o graphs/everything-at-once.svg
plainbox dev special --dot --dot-resources | dot -Tsvg -o graphs/everything-at-once-with-resources.svg
