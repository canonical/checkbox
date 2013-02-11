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
plainbox.impl.job
=================

Internal implementation of plainbox

 * THIS MODULE DOES NOT HAVE STABLE PUBLIC API *
"""

import collections
import hashlib
import json
import logging
import os
import re

from plainbox.abc import IJobDefinition
from plainbox.impl.resource import ResourceProgram


logger = logging.getLogger("plainbox.job")


class JobDefinition(IJobDefinition):

    @property
    def plugin(self):
        return self.__getattr__('plugin')

    @property
    def name(self):
        return self.__getattr__('name')

    @property
    def requires(self):
        try:
            return self.__getattr__('requires')
        except AttributeError:
            return None

    @property
    def command(self):
        try:
            return self.__getattr__('command')
        except AttributeError:
            return None

    @property
    def description(self):
        try:
            return self.__getattr__('description')
        except AttributeError:
            return None

    @property
    def depends(self):
        try:
            return self.__getattr__('depends')
        except AttributeError:
            return None

    @property
    def user(self):
        try:
            return self.__getattr__('user')
        except AttributeError:
            return None

    @property
    def origin(self):
        """
        The Origin object associated with this JobDefinition

        May be None
        """
        return self._origin

    def __init__(self, data, origin=None, checkbox=None):
        self._data = data
        self._resource_program = None
        self._origin = origin
        self._checkbox = checkbox

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<JobDefinition name:{!r} plugin:{!r}>".format(
            self.name, self.plugin)

    def __getattr__(self, attr):
        if attr in self._data:
            return self._data[attr]
        gettext_attr = "_{}".format(attr)
        if gettext_attr in self._data:
            value = self._data[gettext_attr]
            # TODO: feed through gettext
            return value
        raise AttributeError(attr)

    def _get_persistance_subset(self):
        state = {}
        state['data'] = {}
        state['data']['plugin'] = self.plugin
        state['data']['name'] = self.name
        return state

    def get_resource_program(self):
        """
        Return a ResourceProgram based on the 'requires' expression.

        The program instance is cached in the JobDefinition and is not
        compiled or validated on subsequent calls.

        Returns ResourceProgram or None
        Raises ResourceProgramError or SyntaxError
        """
        if self.requires is not None and self._resource_program is None:
            self._resource_program = ResourceProgram(self.requires)
        return self._resource_program

    def get_direct_dependencies(self):
        """
        Compute and return a set of direct dependencies

        To combat a simple mistake where the jobs are space-delimited any
        mixture of white-space (including newlines) and commas are allowed.
        """
        if self.depends:
            return {name for name in re.split('[\s,]+', self.depends)}
        else:
            return set()

    def get_resource_dependencies(self):
        """
        Compute and return a set of resource dependencies
        """
        program = self.get_resource_program()
        if program:
            return program.required_resources
        else:
            return set()

    @classmethod
    def from_rfc822_record(cls, record):
        """
        Create a JobDefinition instance from rfc822 record

        The record must be a RFC822Record instance.

        Only the 'name' and 'plugin' keys are required.
        All other data is stored as is and is entirely optional.
        """
        for key in ['plugin', 'name']:
            if key not in record.data:
                raise ValueError(
                    "Required record key {!r} was not found".format(key))
        return cls(record.data, record.origin)

    def modify_execution_environment(self, env, session_dir):
        """
        Alter execution environment as required to execute this job.

        The environment is modified in place.

        The session_dir argument can be passed to scripts to know where to
        create temporary data. This data will persist during the lifetime of
        the session.

        Computes and modifies the dictionary of additional values that need to
        be added to the base environment. Note that all changes to the
        environment (modifications, not replacements) depend on the current
        environment.  This may be of importance when attempting to setup the
        test session as another user.

        This environment has additional PATH, PYTHONPATH entries. It also uses
        fixed LANG so that scripts behave as expected. Lastly it sets
        CHECKBOX_SHARE that is required by some scripts.
        """
        # XXX: this obviously requires a checkbox object to know where stuff is
        # but during the transition we may not have one available.
        assert self._checkbox is not None
        # Use PATH that can lookup checkbox scripts
        if self._checkbox.extra_PYTHONPATH:
            env['PYTHONPATH'] = os.pathsep.join(
                [self._checkbox.extra_PYTHONPATH]
                + env.get("PYTHONPATH", "").split(os.pathsep))
        # Update PATH so that scripts can be found
        env['PATH'] = os.pathsep.join(
            [self._checkbox.extra_PATH]
            + env.get("PATH", "").split(os.pathsep))
        # Add CHECKBOX_SHARE that is needed by one script
        env['CHECKBOX_SHARE'] = self._checkbox.CHECKBOX_SHARE
        # Add CHECKBOX_DATA (temporary checkbox data)
        env['CHECKBOX_DATA'] = session_dir

    def create_child_job_from_record(self, record):
        """
        Create a new JobDefinition from RFC822 record.

        This method should only be used to create additional jobs from local
        jobs (plugin local). The intent is to encapsulate the sharing of the
        embedded checkbox reference.
        """
        job = self.from_rfc822_record(record)
        job._checkbox = self._checkbox
        return job

    def get_checksum(self):
        """
        Compute a checksum of the job definition.

        This method can be used to compute the checksum of the canonical form
        of the job definition.  The canonical form is the UTF-8 encoded JSON
        serialization of the data that makes up the full definition of the job
        (all keys and values). The JSON serialization uses no indent and
        minimal separators.

        The checksum is defined as the SHA256 hash of the canonical form.
        """
        # Ideally we'd use simplejson.dumps() with sorted keys to get
        # predictable serialization but that's another dependency. To get
        # something simple that is equally reliable, just sort all the keys
        # manually and ask standard json to serialize that..
        sorted_data = collections.OrderedDict(sorted(self._data.items()))
        # Compute the canonical form which is arbitrarily defined as sorted
        # json text with default indent and separator settings.
        canonical_form = json.dumps(
            sorted_data, indent=None, separators=(',', ':'))
        # Compute the sha256 hash of the UTF-8 encoding of the canonical form
        # and return the hex digest as the checksum that can be displayed.
        return hashlib.sha256(canonical_form.encode('UTF-8')).hexdigest()

    @classmethod
    def from_json_record(cls, record):
        """
        Create a JobDefinition instance from JSON record
        """
        return cls(record['data'])
