# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
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
:mod:`plainbox.impl.job` -- job definition
==========================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import logging
import os
import re

from plainbox.abc import IJobDefinition
from plainbox.impl.config import Unset
from plainbox.impl.resource import ResourceProgram
from plainbox.impl.secure.checkbox_trusted_launcher import BaseJob


logger = logging.getLogger("plainbox.job")


class JobDefinition(BaseJob, IJobDefinition):
    """
    Job definition class.

    Thin wrapper around the RFC822 record that defines a checkbox job
    definition
    """

    def get_record_value(self, name, default=None):
        """
        Obtain the value of the specified record attribute
        """
        try:
            return self._data["_{}".format(name)]
        except KeyError:
            return super(JobDefinition, self).get_record_value(name, default)

    @property
    def name(self):
        return self.get_record_value('name')

    @property
    def requires(self):
        return self.get_record_value('requires')

    @property
    def description(self):
        return self.get_record_value('description')

    @property
    def depends(self):
        return self.get_record_value('depends')

    @property
    def estimated_duration(self):
        """
        estimated duration of this job in seconds.

        The value may be None, which indicates that the duration is basically
        unknown. Fractional numbers are allowed and indicate fractions of a
        second.
        """
        value = self.get_record_value('estimated_duration')
        if value is None:
            return
        try:
            return float(value)
        except ValueError:
            logger.warning((
                "Incorrect value of 'estimated_duration' in job"
                "%s read from %s"), self.name, self.origin)

    @property
    def automated(self):
        """
        Whether the job is fully automated and runs without any
        intervention from the user
        """
        return self.plugin in ['shell', 'resource',
                               'attachment', 'local']

    @property
    def via(self):
        """
        The checksum of the "parent" job when the current JobDefinition comes
        from a job output using the local plugin
        """
        return self._via

    @property
    def origin(self):
        """
        The Origin object associated with this JobDefinition

        May be None
        """
        return self._origin

    def __init__(self, data, origin=None, provider=None, via=None):
        super(JobDefinition, self).__init__(data)
        self._resource_program = None
        self._origin = origin
        self._provider = provider
        self._via = via

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<JobDefinition name:{!r} plugin:{!r}>".format(
            self.name, self.plugin)

    def _get_persistance_subset(self):
        state = {}
        state['data'] = {}
        for key, value in self._data.items():
            state['data'][key] = value
        if self.via is not None:
            state['via'] = self.via
        return state

    def __eq__(self, other):
        if not isinstance(other, JobDefinition):
            return False
        return self.get_checksum() == other.get_checksum()

    def __ne__(self, other):
        if not isinstance(other, JobDefinition):
            return True
        return self.get_checksum() != other.get_checksum()

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

    def modify_execution_environment(self, env, session_dir,
                                     checkbox_data_dir, config=None):
        """
        Alter execution environment as required to execute this job.

        The environment is modified in place.

        The session_dir argument can be passed to scripts to know where to
        create temporary data. This data will persist during the lifetime of
        the session.

        The config argument (which defaults to None) should be a PlainBoxConfig
        object. It is used to provide values for missing environment variables
        that are required by the job (as expressed by the environ key in the
        job definition file).

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
        assert self._provider is not None
        # Use PATH that can lookup checkbox scripts
        if self._provider.extra_PYTHONPATH:
            env['PYTHONPATH'] = os.pathsep.join(
                [self._provider.extra_PYTHONPATH]
                + env.get("PYTHONPATH", "").split(os.pathsep))
        # Update PATH so that scripts can be found
        env['PATH'] = os.pathsep.join(
            [self._provider.extra_PATH]
            + env.get("PATH", "").split(os.pathsep))
        # Add CHECKBOX_SHARE that is needed by one script
        env['CHECKBOX_SHARE'] = self._provider.CHECKBOX_SHARE
        # Add CHECKBOX_DATA (temporary checkbox data)
        env['CHECKBOX_DATA'] = checkbox_data_dir
        # Inject additional variables that are requested in the config
        if config is not None and config.environment is not Unset:
            for env_var in config.environment:
                # Don't override anything that is already present in the
                # current environment. This will allow users to customize
                # variables without editing any config files.
                if env_var in env:
                    continue
                # If the environment section of the configuration file has a
                # particular variable then copy it over.
                env[env_var] = config.environment[env_var]

    def create_child_job_from_record(self, record):
        """
        Create a new JobDefinition from RFC822 record.

        This method should only be used to create additional jobs from local
        jobs (plugin local). The intent is two-fold:
        1) to encapsulate the sharing of the embedded checkbox reference.
        2) to set the ``via`` attribute (to aid the trusted launcher)
        """
        job = self.from_rfc822_record(record)
        job._provider = self._provider
        job._via = self.get_checksum()
        return job

    @classmethod
    def from_json_record(cls, record):
        """
        Create a JobDefinition instance from JSON record
        """
        return cls(record['data'], via=record.get('via'))
