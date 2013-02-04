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

"""
plainbox.impl.utils
===================

Internal implementation of plainbox

 * THIS MODULE DOES NOT HAVE STABLE PUBLIC API *
"""

from io import TextIOWrapper
from logging import getLogger

from plainbox.impl.job import JobDefinition
from plainbox.impl.rfc822 import load_rfc822_records


logger = getLogger("plainbox.utils")


def load(somewhere):
    if isinstance(somewhere, str):
        # Load data from a file with the given name
        filename = somewhere
        with open(filename, 'rt', encoding='UTF-8') as stream:
            return load(stream)
    if isinstance(somewhere, TextIOWrapper):
        stream = somewhere
        logger.debug("Loading jobs definitions from %r...", stream.name)
        record_list = load_rfc822_records(stream)
        job_list = []
        for record in record_list:
            job = JobDefinition.from_rfc822_record(record)
            logger.debug("Loaded %r", job)
            job_list.append(job)
        return job_list
    else:
        raise TypeError(
            "Unsupported type of 'somewhere': {!r}".format(
                type(somewhere)))
