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

import functools
import logging
import os
import re

from plainbox.abc import IJobDefinition
from plainbox.abc import ITextSource
from plainbox.impl.resource import ResourceProgram
from plainbox.impl.secure.config import Unset
from plainbox.impl.secure.job import BaseJob
from plainbox.impl.secure.rfc822 import Origin
from plainbox.impl.symbol import SymbolDef


logger = logging.getLogger("plainbox.job")


class Problem(SymbolDef):
    """
    Symbols for each possible problem that a field value may have
    """
    missing = 'missing'
    wrong = 'wrong'
    useless = 'useless'


class ValidationError(ValueError):
    """
    Exception raised by to report jobs with problematic definitions.
    """

    def __init__(self, field, problem):
        self.field = field
        self.problem = problem

    def __str__(self):
        return "Problem with field {}: {}".format(self.field, self.problem)

    def __repr__(self):
        return "ValidationError(field={!r}, problem={!r})".format(
            self.field, self.problem)


class CheckBoxJobValidator:
    """
    Validator for CheckBox jobs.
    """

    @staticmethod
    def validate(job):
        """
        Validate the specified job
        """
        # Check if name is empty
        if job.name is None:
            raise ValidationError(job.fields.name, Problem.missing)
        # Check if plugin is empty
        if job.plugin is None:
            raise ValidationError(job.fields.plugin, Problem.missing)
        # Check if plugin has a good value
        if job.plugin not in JobDefinition.plugin.get_all_symbols():
            raise ValidationError(job.fields.plugin, Problem.wrong)
        # Check if user is given without a command to run
        if job.user is not None and job.command is None:
            raise ValidationError(job.fields.user, Problem.useless)
        # Check if environ is given without a command to run
        if job.environ is not None and job.command is None:
            raise ValidationError(job.fields.environ, Problem.useless)
        # Verify that command is present on a job within the subset that should
        # really have them (shell, local, resource, attachment, user-verify and
        # user-interact)
        if job.plugin in {JobDefinition.plugin.shell,
                          JobDefinition.plugin.local,
                          JobDefinition.plugin.resource,
                          JobDefinition.plugin.attachment,
                          JobDefinition.plugin.user_verify,
                          JobDefinition.plugin.user_interact,
                          JobDefinition.plugin.user_interact_verify}:
            # Check if shell jobs have a command
            if job.command is None:
                raise ValidationError(job.fields.command, Problem.missing)
            # Check if user has a good value
            if job.user not in (None, "root"):
                raise ValidationError(job.fields.user, Problem.wrong)
        # Do some special checks for manual jobs as those should really be
        # fully interactive, non-automated jobs (otherwise they are either
        # user-interact or user-verify)
        if job.plugin == JobDefinition.plugin.manual:
            # Ensure that manual jobs have a description
            if job.description is None:
                raise ValidationError(
                    job.fields.description, Problem.missing)
            # Ensure that manual jobs don't have command
            if job.command is not None:
                raise ValidationError(job.fields.command, Problem.useless)


class propertywithsymbols(property):
    """
    A property that also keeps a group of symbols around
    """

    def __init__(self, fget=None, fset=None, fdel=None, doc=None,
                 symbols=None):
        """
        Initializes the property with the specified values
        """
        super(propertywithsymbols, self).__init__(fget, fset, fdel, doc)
        self.__doc__ = doc
        self.symbols = symbols

    def __getattr__(self, attr):
        """
        Internal implementation detail.

        Exposes all of the attributes of the SymbolDef group as attributes of
        the property. The way __getattr__() works it can never hide any
        existing attributes so it is safe not to break the property.
        """
        return getattr(self.symbols, attr)

    def __call__(self, fget):
        """
        Internal implementation detail.

        Used to construct the decorator with fget defined to the decorated
        function.
        """
        return propertywithsymbols(
            fget, self.fset, self.fdel, self.__doc__, symbols=self.symbols)


@functools.total_ordering
class JobOutputTextSource(ITextSource):
    """
    A :class:`ITextSource` subclass indicating that text came from job output.

    This class is used by
    :meth:`SessionState._gen_rfc822_records_from_io_log()` to allow such
    (generated) jobs to be traced back to the job that generated them.

    :ivar job:
        :class:`plainbox.impl.job.JobDefinition` instance that generated the
        text
    """

    def __init__(self, job):
        self.job = job

    def __str__(self):
        return str(self.job)

    def __repr__(self):
        return "<{} job:{!r}".format(self.__class__.__name__, self.job)

    def __eq__(self, other):
        if isinstance(other, JobOutputTextSource):
            return self.job == other.job
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, JobOutputTextSource):
            return self.job > other.job
        return NotImplemented


class JobDefinition(BaseJob, IJobDefinition):
    """
    Job definition class.

    Thin wrapper around the RFC822 record that defines a checkbox job
    definition
    """

    class fields(SymbolDef):
        """
        Symbols for each field that a JobDefinition can have
        """
        name = 'name'
        plugin = 'plugin'
        command = 'command'
        description = 'description'
        user = 'user'
        environ = 'environ'
        estimated_duration = 'estimated_duration'

    class _PluginValues(SymbolDef):
        """
        Symbols for each value of the JobDefinition.plugin field
        """
        shell = 'shell'
        attachment = 'attachment'
        local = 'local'
        resource = 'resource'
        manual = 'manual'
        user_verify = "user-verify"
        user_interact = "user-interact"
        user_interact_verify = "user-interact-verify"

    @propertywithsymbols(symbols=_PluginValues)
    def plugin(self):
        return self.get_record_value('plugin')

    def get_record_value(self, name, default=None):
        """
        Obtain the value of the specified record attribute
        """
        value = super(JobDefinition, self).get_record_value("_{}".format(name))
        if value is None:
            value = super(JobDefinition, self).get_record_value(name, default)
        return value

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
                " %s read from %s"), self.name, self.origin)

    @property
    def automated(self):
        """
        Whether the job is fully automated and runs without any
        intervention from the user
        """
        return self.plugin in ['shell', 'resource',
                               'attachment', 'local']

    @property
    def startup_user_interaction_required(self):
        """
        The job needs to be started explicitly by the test operator. This is
        intended for things that may be timing-sensitive or may require the
        tester to understand the necessary manipulations that he or she may
        have to perform ahead of time.

        The test operator may select to skip certain tests, in that case the
        outcome is skip.
        """
        return self.plugin in ['manual', 'user-interact',
                               'user-interact-verify']

    @property
    def via(self):
        """
        The checksum of the "parent" job when the current JobDefinition comes
        from a job output using the local plugin
        """
        if hasattr(self.origin.source, 'job'):
            return self.origin.source.job.checksum

    @property
    def origin(self):
        """
        The Origin object associated with this JobDefinition
        """
        return self._origin

    def update_origin(self, origin):
        """
        Change the Origin object associated with this JobDefinition

        .. note::

            This method is a unfortunate side effect of how via and local jobs
            that cat existing jobs are implemented. Ideally jobs would be
            trully immutable. Do not use this method lightly.
        """
        self._origin = origin

    def __init__(self, data, origin=None, provider=None):
        super(JobDefinition, self).__init__(data)
        if origin is None:
            origin = Origin.get_caller_origin()
        self._resource_program = None
        self._origin = origin
        self._provider = provider

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<JobDefinition name:{!r} plugin:{!r}>".format(
            self.name, self.plugin)

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
        if 'name' not in record.data:
            raise ValueError("Cannot create job without a name")
        return cls(record.data, record.origin)

    def validate(self, validator_cls=CheckBoxJobValidator):
        """
        Validate this job definition with the specified validator

        :raises ValidationError:
            If the job has any problems that make it unsuitable for execution.
        """
        validator_cls.validate(self)

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
        jobs (plugin local). This ensures that the child job shares the
        embedded provider reference.
        """
        if not isinstance(record.origin.source, JobOutputTextSource):
            raise ValueError("record.origin must be a JobOutputTextSource")
        if not record.origin.source.job is self:
            raise ValueError("record.origin.source.job must be this job")
        job = self.from_rfc822_record(record)
        job._provider = self._provider
        return job
