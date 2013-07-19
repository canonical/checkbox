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

"""
:mod:`plainbox.impl.service` -- DBus service for PlainBox
=========================================================
"""

import functools
import itertools
import logging

try:
    from inspect import Signature
except ImportError:
    try:
        from plainbox.vendor.funcsigs import Signature
    except ImportError:
        raise SystemExit("DBus parts require 'funcsigs' from pypi.")

from plainbox.impl import dbus
from plainbox.impl.dbus import OBJECT_MANAGER_IFACE
from plainbox.impl.signal import Signal


logger = logging.getLogger("plainbox.service")

_BASE_IFACE = "com.canonical.certification."

SERVICE_IFACE = _BASE_IFACE + "PlainBox.Service1"
SESSION_IFACE = _BASE_IFACE + "PlainBox.Session1"
PROVIDER_IFACE = _BASE_IFACE + "PlainBox.Provider1"
JOB_IFACE = _BASE_IFACE + "PlainBox.JobDefinition1"
JOB_RESULT_IFACE = _BASE_IFACE + "PlainBox.Result1"
JOB_STATE_IFACE = _BASE_IFACE + "PlainBox.JobState1"
WHITELIST_IFACE = _BASE_IFACE + "PlainBox.WhiteList1"
CHECKBOX_JOB_IFACE = _BASE_IFACE + "CheckBox.JobDefinition1"


class PlainBoxObjectWrapper(dbus.service.ObjectWrapper):
    """
    Wrapper for exporting PlainBox object over DBus.

    Allows to keep the python object logic separate from the DBus counterpart.
    Has a set of utility methods to publish the object and any children objects
    to DBus.
    """

    def __init__(self,
                 native,
                 conn=None, object_path=None, bus_name=None,
                 **kwargs):
        super(PlainBoxObjectWrapper, self).__init__(
            native, conn, object_path, bus_name)
        logger.debug("Created DBus wrapper for: %r", self.native)
        self.__shared_initialize__(**kwargs)

    def __shared_initialize__(self, **kwargs):
        """
        Optional initialize method that can use any unused keyword arguments
        that were originally passed to __init__(). This makes it far easier to
        subclass as __init__() is rather complicated.

        Inspired by STANDARD GENERIC FUNCTION SHARED-INITIALIZE
        See hyperspec page: http://clhs.lisp.se/Body/f_shared.htm
        """

    def _get_preferred_object_path(self):
        """
        Return the preferred object path of this object on DBus
        """
        return "/plainbox/{}/{}".format(
            self.native.__class__.__name__, id(self.native))

    def publish_self(self, connection):
        """
        Publish this object to the connection
        """
        object_path = self._get_preferred_object_path()
        self.add_to_connection(connection, object_path)
        logger.debug("Published DBus wrapper for %r as %s",
                     self.native, object_path)

    def publish_objects(self, connection):
        """
        Publish this and any other objects to the connection

        Do not send any events, just register the objects on the bus. By
        default only the object itself is published but collection managers are
        expected to publish all of the children here.
        """
        self.publish_self(connection)

    def publish_children(self):
        """
        This method is specific to ObjectManager, it basically adds children
        and sends the right events.  This is a separate stage so that the whole
        hierarchy can first put all of the objects on the bus and then tell the
        world about it in one big signal message.
        """

    @classmethod
    def translate(cls, func):
        """
        Decorator for Wrapper methods.

        The decorated method does not need to manually lookup objects when the
        caller (across DBus) passes an object path. Type information is
        provided using parameter annotations.

        The annotation accepts DBus type expressions (but in practice it is
        very limited). For the moment it cannot infer the argument types from
        the decorator for dbus.service.method.
        """
        sig = Signature.from_function(func)

        def translate_o(object_path):
            try:
                obj = cls.find_object_by_path(object_path)
            except KeyError as exc:
                raise dbus.exceptions.DBusException((
                    "object path {} does not designate an existing"
                    " object").format(exc))
            else:
                return obj.native

        def translate_ao(object_path_list):
            try:
                obj_list = [cls.find_object_by_path(object_path)
                            for object_path in object_path_list]
            except KeyError as exc:
                raise dbus.exceptions.DBusException((
                    "object path {} does not designate an existing"
                    " object").format(exc))
            else:
                return [obj.native for obj in obj_list]

        def translate_return_o(obj):
            try:
                return cls.find_wrapper_by_native(obj)
            except KeyError:
                raise dbus.exceptions.DBusException(
                    "internal error, unable to lookup object wrapper")

        def translate_return_ao(object_list):
            try:
                return dbus.types.Array([
                    cls.find_wrapper_by_native(obj)
                    for obj in object_list
                ], signature='o')
            except KeyError:
                raise dbus.exceptions.DBusException(
                    "internal error, unable to lookup object wrapper")

        def translate_return_a_brace_so_brace(mapping):
            try:
                return dbus.types.Dictionary({
                    key: cls.find_wrapper_by_native(value)
                    for key, value in mapping.items()
                }, signature='so')
            except KeyError:
                raise dbus.exceptions.DBusException(
                    "internal error, unable to lookup object wrapper")

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            bound = sig.bind(*args, **kwargs)
            logger.debug(
                "wrapped %s called with %s", func, bound.arguments)
            for param in sig.parameters.values():
                if param.annotation is Signature.empty:
                    pass
                elif param.annotation == 'o':
                    object_path = bound.arguments[param.name]
                    bound.arguments[param.name] = translate_o(object_path)
                elif param.annotation == 'ao':
                    object_path_list = bound.arguments[param.name]
                    bound.arguments[param.name] = translate_ao(
                        object_path_list)
                else:
                    raise ValueError(
                        "unsupported translation {!r}".format(
                            param.annotation))
            logger.debug(
                "unwrapped %s called with %s", func, bound.arguments)
            retval = func(**bound.arguments)
            logger.debug("unwrapped %s returned %r", func, retval)
            if sig.return_annotation is Signature.empty:
                pass
            elif sig.return_annotation == 'o':
                retval = translate_return_o(retval)
            elif sig.return_annotation == 'ao':
                retval = translate_return_ao(retval)
            elif sig.return_annotation == 'a{so}':
                retval = translate_return_a_brace_so_brace(retval)
            else:
                raise ValueError(
                    "unsupported translation {!r}".format(
                        sig.return_annotation))
            logger.debug("wrapped %s returned  %r", func, retval)
            return retval
        return wrapper


class JobDefinitionWrapper(PlainBoxObjectWrapper):
    """
    Wrapper for exposing JobDefinition objects on DBus
    """

    HIDDEN_INTERFACES = frozenset([
        OBJECT_MANAGER_IFACE,
    ])

    # Some internal helpers

    def __shared_initialize__(self, **kwargs):
        self._checksum = self.native.get_checksum()

    def _get_preferred_object_path(self):
        # TODO: this clashes with providers, maybe use a random ID instead
        return "/plainbox/job/{}".format(self._checksum)

    # PlainBox properties

    @dbus.service.property(dbus_interface=JOB_IFACE, signature="s")
    def name(self):
        return self.native.name

    @dbus.service.property(dbus_interface=JOB_IFACE, signature="s")
    def description(self):
        return self.native.description or ""

    @dbus.service.property(dbus_interface=JOB_IFACE, signature="s")
    def checksum(self):
        # This is a bit expensive to compute so let's keep it cached
        return self._checksum

    @dbus.service.property(dbus_interface=JOB_IFACE, signature="s")
    def requires(self):
        return self.native.requires or ""

    @dbus.service.property(dbus_interface=JOB_IFACE, signature="s")
    def depends(self):
        return self.native.depends or ""

    @dbus.service.property(dbus_interface=JOB_IFACE, signature="d")
    def estimated_duration(self):
        return self.native.estimated_duration or -1

    # PlainBox methods

    @dbus.service.method(dbus_interface=JOB_IFACE,
                         in_signature='', out_signature='as')
    def GetDirectDependencies(self):
        return self.native.get_direct_dependencies()

    @dbus.service.method(dbus_interface=JOB_IFACE,
                         in_signature='', out_signature='as')
    def GetResourceDependencies(self):
        return self.native.get_resource_dependencies()

    @dbus.service.method(dbus_interface=CHECKBOX_JOB_IFACE,
                         in_signature='', out_signature='as')
    def GetEnvironSettings(self):
        return self.native.get_environ_settings()

    # CheckBox properties

    @dbus.service.property(dbus_interface=CHECKBOX_JOB_IFACE, signature="s")
    def plugin(self):
        return self.native.plugin

    @dbus.service.property(dbus_interface=CHECKBOX_JOB_IFACE, signature="s")
    def via(self):
        return self.native.via or ""

    @dbus.service.property(
        dbus_interface=CHECKBOX_JOB_IFACE, signature="(suu)")
    def origin(self):
        if self.native.origin is not None:
            return dbus.Struct([
                self.native.origin.filename,
                self.native.origin.line_start,
                self.native.origin.line_end
            ], signature="suu")
        else:
            return dbus.Struct(["", 0, 0], signature="suu")

    @dbus.service.property(dbus_interface=CHECKBOX_JOB_IFACE, signature="s")
    def command(self):
        return self.native.command or ""

    @dbus.service.property(dbus_interface=CHECKBOX_JOB_IFACE, signature="s")
    def environ(self):
        return self.native.environ or ""

    @dbus.service.property(dbus_interface=CHECKBOX_JOB_IFACE, signature="s")
    def user(self):
        return self.native.user or ""


class WhiteListWrapper(PlainBoxObjectWrapper):
    """
    Wrapper for exposing WhiteList objects on DBus
    """

    HIDDEN_INTERFACES = frozenset([
        OBJECT_MANAGER_IFACE,
    ])

    # Some internal helpers

    def _get_preferred_object_path(self):
        # TODO: this clashes with providers, maybe use a random ID instead
        return "/plainbox/whitelist/{}".format(self.native.name)

    # Value added

    @dbus.service.property(dbus_interface=WHITELIST_IFACE, signature="s")
    def name(self):
        """
        name of this whitelist
        """
        return self.native.name or ""

    @dbus.service.method(
        dbus_interface=WHITELIST_IFACE, in_signature='', out_signature='as')
    def GetPatternList(self):
        """
        Get a list of regular expression patterns that make up this whitelist
        """
        return [qualifier.pattern_text
                for qualifier in self.native.inclusive_qualifier_list]

    @dbus.service.method(
        dbus_interface=WHITELIST_IFACE, in_signature='o', out_signature='b')
    @PlainBoxObjectWrapper.translate
    def Designates(self, job: 'o'):
        return self.native.designates(job)


class JobResultWrapper(PlainBoxObjectWrapper):
    """
    Wrapper for exposing JobResult objects on DBus
    """

    HIDDEN_INTERFACES = frozenset([
        OBJECT_MANAGER_IFACE,
    ])

    def __shared_initialize__(self, **kwargs):
        self.native.on_comments_changed.connect(self.on_comments_changed)

    def __del__(self):
        self.native.on_comments_changed.disconnect(self.on_comments_changed)

    # Value added

    @dbus.service.property(dbus_interface=JOB_RESULT_IFACE, signature="s")
    def outcome(self):
        """
        outcome of the job

        The result is one of a set of fixed strings
        """
        # XXX: it would be nice if we could not do this remapping.
        return self.native.outcome or "none"

    @dbus.service.property(dbus_interface=JOB_RESULT_IFACE, signature="i")
    def return_code(self):
        """
        return code of the called program
        """
        value = self.native.return_code
        if value is None:
            raise dbus.exceptions.DBusException("There is no return code yet")
        return value

    # comments are settable, useful thing that

    @dbus.service.property(dbus_interface=JOB_RESULT_IFACE, signature="s")
    def comments(self):
        """
        Comment added by the operator
        """
        return self.native.comments or ""

    @comments.setter
    def comments(self, value):
        self.native.comments = value

    @Signal.define
    def on_comments_changed(self, old, new):
        logger.debug("on_comments_changed(%r, %r)", old, new)
        self.PropertiesChanged(JOB_RESULT_IFACE, {
            self.__class__.comments._dbus_property: new
        }, [])

    @dbus.service.property(
        dbus_interface=JOB_RESULT_IFACE, signature="a(dsay)")
    def io_log(self):
        """
        The input-output log.

        Contains a record of all of the output (actually,
        it has no input logs) that was sent by the called program.

        The format is: array<struct<double, string, array<bytes>>>
        """
        return dbus.types.Array(self.native.io_log, signature="(dsay)")


class JobStateWrapper(PlainBoxObjectWrapper):
    """
    Wrapper for exposing JobState objects on DBus
    """

    HIDDEN_INTERFACES = frozenset([
        OBJECT_MANAGER_IFACE,
    ])

    def __shared_initialize__(self, **kwargs):
        self._result_wrapper = JobResultWrapper(self.native.result)

    def publish_objects(self, connection):
        super(JobStateWrapper, self).publish_objects(connection)
        self._result_wrapper.publish_objects(connection)

    # Value added

    @dbus.service.method(
        dbus_interface=JOB_STATE_IFACE, in_signature='', out_signature='b')
    def CanStart(self):
        """
        Quickly check if the associated job can run right now.
        """
        return self.native.can_start()

    @dbus.service.method(
        dbus_interface=JOB_STATE_IFACE, in_signature='', out_signature='s')
    def GetReadinessDescription(self):
        """
        Get a human readable description of the current readiness state
        """
        return self.native.get_readiness_description()

    @dbus.service.property(dbus_interface=JOB_STATE_IFACE, signature='o')
    @PlainBoxObjectWrapper.translate
    def job(self) -> 'o':
        """
        Job associated with this state
        """
        return self.native.job

    @dbus.service.property(dbus_interface=JOB_STATE_IFACE, signature='o')
    @PlainBoxObjectWrapper.translate
    def result(self) -> 'o':
        """
        Result of running the associated job
        """
        return self.native.result

    # TODO: signal<result>

    @dbus.service.property(dbus_interface=JOB_STATE_IFACE, signature='a(isss)')
    def readiness_inhibitor_list(self):
        """
        The list of readiness inhibitors of the associated job

        The list is represented as an array of structures. Each structure
        has a integer and two strings. The integer encodes the cause
        of inhibition.

        Cause may have one of the following values:

        0 - UNDESIRED:
            This job was not selected to run in this session

        1 - PENDING_DEP:
           This job depends on another job which was not started yet

        2 - FAILED_DEP:
            This job depends on another job which was started and failed

        3 - PENDING_RESOURCE:
            This job has a resource requirement expression that uses a resource
            produced by another job which was not started yet

        4 - FAILED_RESOURCE:
            This job has a resource requirement that evaluated to a false value

        The next two strings are the name of the related job and the name
        of the related expression. Either may be empty.
        """
        return dbus.types.Array([
            (inhibitor.cause,
             inhibitor.cause_name,
             (inhibitor.related_job.name
              if inhibitor.related_job is not None else ""),
             (inhibitor.related_expression
              if inhibitor.related_expression is not None else ""))
            for inhibitor in self.native.readiness_inhibitor_list
        ], signature="(isss)")


class SessionWrapper(PlainBoxObjectWrapper):
    """
    Wrapper for exposing SessionState objects on DBus
    """

    HIDDEN_INTERFACES = frozenset()

    # XXX: those will change to SessionManager later and session state will be
    # a part of that (along with session storage)

    def __shared_initialize__(self, **kwargs):
        self._job_state_map_wrapper = {
            job_name: JobStateWrapper(job_state)
            for job_name, job_state in self.native.job_state_map.items()
        }

    def publish_objects(self, connection):
        self.publish_self(connection)
        for job_state in self._job_state_map_wrapper.values():
            job_state.publish_objects(connection)

    def publish_children(self):
        wrapper_list = list(self._iter_wrappers())
        self.add_managed_object_list(wrapper_list)
        for wrapper in wrapper_list:
            wrapper.publish_children()

    def _iter_wrappers(self):
        return itertools.chain(
            # Get all of the JobResult wrappers
            self._job_state_map_wrapper.values(),
            # And all the JobDefinition wrappers
            [self.find_wrapper_by_native(job_state_wrapper.native.result)
             for job_state_wrapper in self._job_state_map_wrapper.values()])

    # Value added

    @dbus.service.method(
        dbus_interface=SESSION_IFACE, in_signature='ao', out_signature='as')
    @PlainBoxObjectWrapper.translate
    def UpdateDesiredJobList(self, desired_job_list: 'ao'):
        problem_list = self.native.update_desired_job_list(desired_job_list)
        # TODO: map each problem into a structure (check which fields should be
        # presented). Document this in the docstring.
        return [str(problem) for problem in problem_list]

    @dbus.service.method(
        dbus_interface=SESSION_IFACE, in_signature='oo', out_signature='')
    @PlainBoxObjectWrapper.translate
    def UpdateJobResult(self, job: 'o', result: 'o'):
        self.native.update_job_result(job, result)

    @dbus.service.method(
        dbus_interface=SESSION_IFACE, in_signature='', out_signature='(dd)')
    def GetEstimatedDuration(self):
        automated, manual = self.native.get_estimated_duration()
        if automated is None:
            automated = -1
        if manual is None:
            automated = -1
        return automated, manual

    @dbus.service.property(dbus_interface=SESSION_IFACE, signature='ao')
    @PlainBoxObjectWrapper.translate
    def job_list(self) -> 'ao':
        return self.native.job_list

    # TODO: signal<run_list>

    @dbus.service.property(dbus_interface=SESSION_IFACE, signature='ao')
    @PlainBoxObjectWrapper.translate
    def desired_job_list(self) -> 'ao':
        return self.native.desired_job_list

    # TODO: signal<run_list>

    @dbus.service.property(dbus_interface=SESSION_IFACE, signature='ao')
    @PlainBoxObjectWrapper.translate
    def run_list(self) -> 'ao':
        return self.native.run_list

    # TODO: signal<run_list>

    @dbus.service.property(dbus_interface=SESSION_IFACE, signature='a{so}')
    @PlainBoxObjectWrapper.translate
    def job_state_map(self) -> 'a{so}':
        return self.native.job_state_map

    # TODO: signal<job_state_map>

    @dbus.service.property(dbus_interface=SESSION_IFACE, signature='a{sv}')
    def metadata(self):
        return dbus.types.Dictionary({
            'title': self.native.metadata.title or "",
            'flags': dbus.types.Array(
                sorted(self.native.metadata.flags), signature='s'),
            'running_job_name': self.native.metadata.running_job_name or ""
        }, signature="sv")

    # TODO: signal<metadata>
    # TODO: setter<metadata>


class ProviderWrapper(PlainBoxObjectWrapper):
    """
    Wrapper for exposing Provider1 objects on DBus
    """

    HIDDEN_INTERFACES = frozenset()

    def __shared_initialize__(self, **kwargs):
        self._job_wrapper_list = [
            JobDefinitionWrapper(job)
            for job in self.native.get_builtin_jobs()]
        self._whitelist_wrapper_list = [
            WhiteListWrapper(whitelist)
            for whitelist in self.native.get_builtin_whitelists()]

    def _get_preferred_object_path(self):
        return "/plainbox/provider/{}".format(self.native.name)

    def publish_objects(self, connection):
        super(ProviderWrapper, self).publish_objects(connection)
        wrapper_list = list(self._iter_wrappers())
        for wrapper in wrapper_list:
            wrapper.publish_objects(connection)

    def publish_children(self):
        wrapper_list = list(self._iter_wrappers())
        self.add_managed_object_list(wrapper_list)

    def _iter_wrappers(self):
        return itertools.chain(
            self._job_wrapper_list,
            self._whitelist_wrapper_list)

    # Value added

    @dbus.service.property(dbus_interface=PROVIDER_IFACE, signature="s")
    def name(self):
        """
        name of this provider
        """
        return self.native.name

    @dbus.service.property(dbus_interface=PROVIDER_IFACE, signature="s")
    def description(self):
        """
        description of this provider
        """
        return self.native.description


class ServiceWrapper(PlainBoxObjectWrapper):
    """
    Wrapper for exposing Service objects on DBus
    """

    HIDDEN_INTERFACES = frozenset()

    # Internal setup stuff

    def __shared_initialize__(self, on_exit, **kwargs):
        self._on_exit = on_exit
        self._provider_wrapper_list = [
            ProviderWrapper(provider)
            for provider in self.native.provider_list]

    def _get_preferred_object_path(self):
        return "/plainbox/service1"

    def publish_objects(self, connection):
        super(ServiceWrapper, self).publish_objects(connection)
        for wrapper in self._provider_wrapper_list:
            wrapper.publish_objects(connection)

    def publish_children(self):
        # First publish all of our providers
        self.add_managed_object_list(self._provider_wrapper_list)
        # Then ask the providers to publish their own objects
        for wrapper in self._provider_wrapper_list:
            wrapper.publish_children()

    # Value added

    @dbus.service.property(dbus_interface=SERVICE_IFACE, signature="s")
    def version(self):
        """
        version of this provider
        """
        return self.native.version

    @dbus.service.method(
        dbus_interface=SERVICE_IFACE, in_signature='', out_signature='')
    def Exit(self):
        """
        Shut down the service and terminate
        """
        # TODO: raise exception when job is in progress
        self._on_exit()

    @dbus.service.method(
        dbus_interface=SERVICE_IFACE, in_signature='ao', out_signature='o')
    @PlainBoxObjectWrapper.translate
    def CreateSession(self, job_list: 'ao'):
        # Create a session
        session_obj = self.native.create_session(job_list)
        # Wrap it
        session_wrp = SessionWrapper(session_obj)
        # Publish all objects
        session_wrp.publish_objects(self.connection)
        # Announce the session is there
        self.add_managed_object(session_wrp)
        # Announce any session children
        session_wrp.publish_children()
        # Return the session wrapper back
        return session_wrp
