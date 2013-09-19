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

from threading import Thread
import collections
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
from plainbox.vendor import extcmd

from plainbox.abc import IJobResult
from plainbox.impl import dbus
from plainbox.impl.dbus import OBJECT_MANAGER_IFACE
from plainbox.impl.job import JobDefinition
from plainbox.impl.result import DiskJobResult
from plainbox.impl.runner import JobRunner
from plainbox.impl.session import JobState

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
RUNNING_JOB_IFACE = _BASE_IFACE + "PlainBox.RunningJob1"


class PlainBoxObjectWrapper(dbus.service.ObjectWrapper):
    """
    Wrapper for exporting PlainBox object over DBus.

    Allows to keep the python object logic separate from the DBus counterpart.
    Has a set of utility methods to publish the object and any children objects
    to DBus.
    """

    # Use a different logger for the translate decorator.
    # This is just so that we don't spam people that want to peek
    # at the service module.
    _logger = logging.getLogger("plainbox.dbus.service.translate")

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
        # Don't publish this object if it's already on the required connection
        # TODO: check if we can just drop this test and publish unconditionally
        try:
            if self.connection is connection:
                return
        except AttributeError:
            pass
        object_path = self._get_preferred_object_path()
        self.add_to_connection(connection, object_path)
        logger.debug("Published DBus wrapper for %r as %s",
                     self.native, object_path)

    def publish_related_objects(self, connection):
        """
        Publish this and any other objects to the connection

        Do not send ObjectManager events, just register any additional objects
        on the bus. By default only the object itself is published but
        collection managers are expected to publish all of the children here.

        This method is meant to be called only once, soon after the object
        is constructed but before :meth:`publish_managed_objects()` is called.
        """
        self.publish_self(connection)

    def publish_managed_objects(self):
        """
        This method is specific to ObjectManager, it basically adds children
        and sends the right events. This is a separate stage so that the whole
        hierarchy can first put all of the objects on the bus and then tell the
        world about it in one big signal message.

        This method is meant to be called only once, soon after
        :meth:`publish_related_objects()` was called.
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
                    "(o) internal error, unable to lookup object wrapper")

        def translate_return_ao(object_list):
            try:
                return dbus.types.Array([
                    cls.find_wrapper_by_native(obj)
                    for obj in object_list
                ], signature='o')
            except KeyError:
                raise dbus.exceptions.DBusException(
                    "(ao) internal error, unable to lookup object wrapper")

        def translate_return_a_brace_so_brace(mapping):
            try:
                return dbus.types.Dictionary({
                    key: cls.find_wrapper_by_native(value)
                    for key, value in mapping.items()
                }, signature='so')
            except KeyError:
                raise dbus.exceptions.DBusException(
                    "(a{so}) internal error, unable to lookup object wrapper")

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            bound = sig.bind(*args, **kwargs)
            cls._logger.debug(
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
                elif param.annotation in ('s', 'as'):
                    strings = bound.arguments[param.name]
                    bound.arguments[param.name] = strings
                else:
                    raise ValueError(
                        "unsupported translation {!r}".format(
                            param.annotation))
            cls._logger.debug(
                "unwrapped %s called with %s", func, bound.arguments)
            retval = func(**bound.arguments)
            cls._logger.debug("unwrapped %s returned %r", func, retval)
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
            cls._logger.debug("wrapped %s returned  %r", func, retval)
            return retval
        return wrapper


class JobDefinitionWrapper(PlainBoxObjectWrapper):
    """
    Wrapper for exposing JobDefinition objects on DBus.

    .. note::
        Life cycle of JobDefinition wrappers is associated _either_
        with a Provider wrapper or with a Session wrapper, depending
        on if the job itself is generated or not.
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
        return dbus.Array(
            self.native.get_direct_dependencies(), signature="s")

    @dbus.service.method(dbus_interface=JOB_IFACE,
                         in_signature='', out_signature='as')
    def GetResourceDependencies(self):
        return dbus.Array(
            self.native.get_resource_dependencies(), signature="s")

    @dbus.service.method(dbus_interface=CHECKBOX_JOB_IFACE,
                         in_signature='', out_signature='as')
    def GetEnvironSettings(self):
        return dbus.Array(self.native.get_environ_settings(), signature='s')

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
        return "/plainbox/whitelist/{}".format(
            self.native.name.replace("-", "_"))

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
        return dbus.Array([
            qualifier.pattern_text
            for qualifier in self.native.inclusive_qualifier_list],
            signature='s')

    @dbus.service.method(
        dbus_interface=WHITELIST_IFACE, in_signature='o', out_signature='b')
    @PlainBoxObjectWrapper.translate
    def Designates(self, job: 'o'):
        return self.native.designates(job)


class JobResultWrapper(PlainBoxObjectWrapper):
    """
    Wrapper for exposing JobResult objects on DBus.

    This wrapper class exposes two mutable properties, 'outcome'
    and 'comments'. Changing them either through native python APIs
    or through DBus property API will result in synchronized updates
    as well as property change notification signals being sent.
    """

    HIDDEN_INTERFACES = frozenset([
        OBJECT_MANAGER_IFACE,
    ])

    def __shared_initialize__(self, **kwargs):
        self.native.on_outcome_changed.connect(self._outcome_changed)
        self.native.on_comments_changed.connect(self._comments_changed)

    def __del__(self):
        self.native.on_comments_changed.disconnect(self._comments_changed)
        self.native.on_outcome_changed.disconnect(self._outcome_changed)

    # Value added

    @dbus.service.property(dbus_interface=JOB_RESULT_IFACE, signature="s")
    def outcome(self):
        """
        outcome of the job

        The result is one of a set of fixed strings.
        """
        # XXX: it would be nice if we could not do this remapping.
        return self.native.outcome or "none"

    @outcome.setter
    def outcome(self, new_value):
        """
        set outcome of the job to a new value
        """
        # XXX: it would be nice if we could not do this remapping.
        if new_value == "none":
            new_value = None
        self.native.outcome = new_value

    def _outcome_changed(self, old, new):
        """
        Internal method called when the value of self.native.outcome changes

        It sends the DBus PropertiesChanged signal for the 'outcome' property.
        """
        self.PropertiesChanged(JOB_RESULT_IFACE, {
            self.__class__.outcome._dbus_property: new
        }, [])

    @dbus.service.property(dbus_interface=JOB_RESULT_IFACE, signature="d")
    def execution_duration(self):
        """
        The amount of time in seconds it took to run this jobs command.

        :returns:
            The value of execution_duration or -1.0 if the command was not
            executed yet.
        """
        execution_duration = self.native.execution_duration
        if execution_duration is None:
            return -1.0
        else:
            return execution_duration

    @dbus.service.property(dbus_interface=JOB_RESULT_IFACE, signature="v")
    def return_code(self):
        """
        return code of the called program
        """
        value = self.native.return_code
        if value is None:
            return ""
        else:
            return value

    # comments are settable, useful thing that

    @dbus.service.property(dbus_interface=JOB_RESULT_IFACE, signature="s")
    def comments(self):
        """
        comment added by the operator
        """
        return self.native.comments or ""

    @comments.setter
    def comments(self, value):
        """
        set comments to a new value
        """
        self.native.comments = value

    def _comments_changed(self, old, new):
        """
        Internal method called when the value of self.native.comments changes

        It sends the DBus PropertiesChanged signal for the 'comments' property.
        """
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
        return dbus.types.Array(self.native.get_io_log(), signature="(dsay)")


class JobStateWrapper(PlainBoxObjectWrapper):
    """
    Wrapper for exposing JobState objects on DBus.

    Each job state wrapper has two related objects, job definition and job
    result. The job state wrapper itself is not a object manager so all of
    the managed objects belong in the session this job state is associated
    with.

    The job property is immutable. The result property is mutable but only
    through native python API. Any changes to the result property are
    propagated to changes in the DBus layer. When the 'result' property
    changes it is not reflecting changes of the object referenced by that
    property (those are separate) but instead indicates that the whole
    referenced object has been replaced by another object.

    Since JobStateWrapper is not an ObjectManager it does not manage the
    exact lifecycle and does not keep a collection that would reference
    the various result objects it must delegate this task to an instance
    of SessionWrapper (the instance that it is associated with).
    """

    HIDDEN_INTERFACES = frozenset([
        OBJECT_MANAGER_IFACE,
    ])

    def __shared_initialize__(self, session_wrapper, **kwargs):
        # We need a reference to the session wrapper so that we can
        # react to result changes.
        self._session_wrapper = session_wrapper
        # Let's cache (and hold) references to the wrappers that
        # we should know about. This keeps them in the live set and makes
        # accessing relevant properties faster.
        self._result_wrapper = self.find_wrapper_by_native(self.native.result)
        self._job_wrapper = self.find_wrapper_by_native(self.native.job)
        # Connect to the on_result_changed signal so that we can keep the
        # referenced 'result' wrapper in sync with the native result object.
        self.native.on_result_changed.connect(self._result_changed)

    def __del__(self):
        self.native.on_result_changed.disconnect(self._result_changed)

    def publish_related_objects(self, connection):
        super(JobStateWrapper, self).publish_related_objects(connection)
        self._result_wrapper.publish_related_objects(connection)
        self._job_wrapper.publish_related_objects(connection)

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

    def _result_changed(self, old, new):
        """
        Internal method called when the value of self.native.comments changes

        It ensures that we have appropriate wrapper for the new result wrapper
        and that it is properly accounted for by the session. It also sends
        the DBus PropertiesChanged signal for the 'result' property.
        """
        # Add the new result object
        result_wrapper = self._session_wrapper.add_result(new)
        # Notify applications that the result property has changed
        self.PropertiesChanged(JOB_STATE_IFACE, {
            self.__class__.result._dbus_property: result_wrapper
        }, [])
        # Remove the old result object
        self._session_wrapper.remove_result(old)

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
             (inhibitor.related_expression.text
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
        # Wrap the initial set of objects reachable via the session state map
        # We don't use the add_{job,result,state}() methods as they also
        # change managed_object_list and we just want to send one big event
        # rather than a storm of tiny events.
        self._job_state_map_wrapper = {}
        for job_name, job_state in self.native.job_state_map.items():
            # NOTE: we assume that each job is already wrapped by its provider
            job_wrapper = self.find_wrapper_by_native(job_state.job)
            assert job_wrapper is not None
            # Wrap the result and the state object
            result_wrapper = self._maybe_wrap(job_state.result)
            assert result_wrapper is not None
            state_wrapper = self._maybe_wrap(job_state)
            self._job_state_map_wrapper[job_name] = state_wrapper
        # Keep track of new jobs as they are added to the session
        self.native.on_job_added.connect(self._job_added)

    def __del__(self):
        self.native.on_job_added.disconnect(self._job_added)
        for wrapper in self.managed_objects:
            wrapper.remove_from_connection()

    def publish_related_objects(self, connection):
        super(SessionWrapper, self).publish_related_objects(connection)
        # Publish all the JobState wrappers and their related objects
        for job_state in self._job_state_map_wrapper.values():
            job_state.publish_related_objects(connection)

    def publish_managed_objects(self):
        wrapper_list = list(self._iter_wrappers())
        self.add_managed_object_list(wrapper_list)
        for wrapper in wrapper_list:
            wrapper.publish_managed_objects()

    def _iter_wrappers(self):
        return itertools.chain(
            # Get all of the JobState wrappers
            self._job_state_map_wrapper.values(),
            # And all the JobResult wrappers
            [self.find_wrapper_by_native(job_state_wrapper.native.result)
             for job_state_wrapper in self._job_state_map_wrapper.values()])

    def add_result(self, result):
        """
        Add a result representation to DBus.

        Take a IJobResult subclass instance, wrap it in JobResultWrapper,
        publish it so that it shows up on DBus, add it to the collection
        of objects managed by this SessionWrapper so that it sends
        InterfacesAdded signals and can be enumerated with
        GetManagedObjects() and return the wrapper to the caller.

        :returns:
            The wrapper for the result that was added
        """
        logger.info("Adding result %r to DBus", result)
        result_wrapper = self._maybe_wrap(result)
        result_wrapper.publish_self(self.connection)
        self.add_managed_object(result_wrapper)
        return result_wrapper

    def remove_result(self, result):
        """
        Remove a result representation from DBus.

        Take a IJobResult subclass instance, find the JobResultWrapper that
        it is wrapped in. Remove it from the collection of objects managed
        by this SessionWrapper so that it sends InterfacesRemoved signal
        and can no longer be enumerated with GetManagedObjects(), remove it
        from the bus and return the wrapper to the caller.

        :returns:
            The wrapper for the result that was removed
        """
        logger.info("Removing result %r from DBus", result)
        result_wrapper = self.find_wrapper_by_native(result)
        self.remove_managed_object(result_wrapper)
        result_wrapper.remove_from_connection()
        return result_wrapper

    def add_job(self, job):
        """
        Add a job representation to DBus.

        :param job:
            Job to add to the bus
        :ptype job:
            JobDefinition

        Take a JobDefinition, wrap it in JobResultWrapper, publish it so that
        it shows up on DBus, add it to the collection of objects managed by
        this SessionWrapper so that it sends InterfacesAdded signals and
        can be enumerated with GetManagedObjects.

        :returns:
            The wrapper for the job that was added
        """
        logger.info("Adding job %r to DBus", job)
        job_wrapper = self._maybe_wrap(job)
        job_wrapper.publish_self(self.connection)
        self.add_managed_object(job_wrapper)
        return job_wrapper

    def add_state(self, state):
        """
        Add a job state representatio to DBus.

        :param state:
            Job state to add to the bus
        :ptype state:
            JobState

        Take a JobState, wrap it in JobStateWrapper, publish it so that
        it shows up on DBus, add it to the collection of objects managed by
        this SessionWrapper so that it sends InterfacesAdded signals and
        can be enumerated with GetManagedObjects.

        .. note::
            This method must be called after both result and job definition
            have been added (presumably with :meth:`add_job()` and
            :meth:`add_result()`). This method *does not* publish those
            objects, it only publishes the state object.

        :returns:
            The wrapper for the job that was added

        """
        logger.info("Adding job state %r to DBus", state)
        state_wrapper = self._maybe_wrap(state)
        state_wrapper.publish_self(self.connection)
        self.add_managed_object(state_wrapper)
        return state_wrapper

    def _maybe_wrap(self, obj):
        """
        Wrap a native object in the appropriate DBus wrapper.

        :param obj:
            The object to wrap
        :ptype obj:
            JobDefinition, IJobResult or JobState
        :returns:
            The wrapper associated with the object

        The object is only wrapped if it was not wrapped previously (at most
        one wrapper is created for any given native object). Only a few classes
        are supported, those are JobDefinition, IJobResult, JobState.
        """
        try:
            return self.find_wrapper_by_native(obj)
        except LookupError:
            if isinstance(obj, JobDefinition):
                return JobDefinitionWrapper(obj)
            elif isinstance(obj, IJobResult):
                return JobResultWrapper(obj)
            elif isinstance(obj, JobState):
                return JobStateWrapper(obj, session_wrapper=self)
            else:
                raise TypeError("Unable to wrap object of type %r" % type(obj))

    def _job_added(self, job):
        """
        Internal method connected to the SessionState.on_job_added() signal.

        This method is called when a generated job is added to the session.
        This method adds the corresponding job definition, job result and
        job state to the bus and sends appropriate notifications.
        """
        logger.debug("_job_added(%r)", job)
        # Get references to the three key objects, job, state and result
        state = self.native.job_state_map[job.name]
        result = state.result
        assert job is state.job
        # Wrap them in the right order (state has to be last)
        self.add_job(job)
        self.add_result(result)
        state_wrapper = self.add_state(state)
        # Update the job_state_map wrapper that we have here
        self._job_state_map_wrapper[job.name] = state_wrapper
        # Send the signal that the 'job_state_map' property has changed
        self.PropertiesChanged(SESSION_IFACE, {
            self.__class__.job_state_map._dbus_property:
            self._job_state_map_wrapper
        }, [])

    # Value added

    @dbus.service.method(
        dbus_interface=SESSION_IFACE, in_signature='ao', out_signature='as')
    @PlainBoxObjectWrapper.translate
    def UpdateDesiredJobList(self, desired_job_list: 'ao'):
        logger.info("UpdateDesiredJobList(%r)", desired_job_list)
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
            automated = -1.0
        if manual is None:
            manual = -1.0
        return automated, manual

    @dbus.service.method(
        dbus_interface=SESSION_IFACE, in_signature='', out_signature='s')
    def PreviousSessionFile(self):
        previous_session_file = self.native.previous_session_file()
        if previous_session_file:
            return previous_session_file
        else:
            return ''

    @dbus.service.method(
        dbus_interface=SESSION_IFACE, in_signature='', out_signature='')
    def Resume(self):
        self.native.resume()

    @dbus.service.method(
        dbus_interface=SESSION_IFACE, in_signature='', out_signature='')
    def Clean(self):
        self.native.clean()

    @dbus.service.method(
        dbus_interface=SESSION_IFACE, in_signature='', out_signature='')
    def PersistentSave(self):
        self.native.persistent_save()

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

    @dbus.service.property(dbus_interface=SESSION_IFACE, signature='a{sv}')
    def metadata(self):
        return dbus.types.Dictionary({
            'title': self.native.metadata.title or "",
            'flags': dbus.types.Array(
                sorted(self.native.metadata.flags), signature='s'),
            'running_job_name': self.native.metadata.running_job_name or "",
            'app_blob': self.native.metadata.app_blob or b''
        }, signature="sv")

    @metadata.setter
    def metadata(self, value):
        self.native.metadata.title = value['title']
        self.native.metadata.running_job_name = value['running_job_name']
        self.native.metadata.flags = value['flags']
        self.native.metadata.app_blob = value.get('app_blob', b'')


    # TODO: signal<metadata>


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

    def publish_related_objects(self, connection):
        super(ProviderWrapper, self).publish_related_objects(connection)
        wrapper_list = list(self._iter_wrappers())
        for wrapper in wrapper_list:
            wrapper.publish_related_objects(connection)

    def publish_managed_objects(self):
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

    def publish_related_objects(self, connection):
        super(ServiceWrapper, self).publish_related_objects(connection)
        for wrapper in self._provider_wrapper_list:
            wrapper.publish_related_objects(connection)

    def publish_managed_objects(self):
        # First publish all of our providers
        self.add_managed_object_list(self._provider_wrapper_list)
        # Then ask the providers to publish their own objects
        for wrapper in self._provider_wrapper_list:
            wrapper.publish_managed_objects()

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
        dbus_interface=SERVICE_IFACE, in_signature='', out_signature='a{sas}')
    def GetAllExporters(self):
        """
        Get all exporters names and their respective options
        """
        return self.native.get_all_exporters()

    @dbus.service.method(
        dbus_interface=SERVICE_IFACE, in_signature='osas', out_signature='s')
    @PlainBoxObjectWrapper.translate
    def ExportSession(self, session: 'o', output_format: 's',
                      option_list: 'as'):
        return self.native.export_session(session, output_format, option_list)

    @dbus.service.method(
        dbus_interface=SERVICE_IFACE, in_signature='osass', out_signature='s')
    @PlainBoxObjectWrapper.translate
    def ExportSessionToFile(self, session: 'o', output_format: 's',
                            option_list: 'as', output_file: 's'):
        return self.native.export_session_to_file(
            session, output_format, option_list, output_file)

    @dbus.service.method(
        dbus_interface=SERVICE_IFACE, in_signature='ao', out_signature='o')
    @PlainBoxObjectWrapper.translate
    def CreateSession(self, job_list: 'ao'):
        # Create a session
        session_obj = self.native.create_session(job_list)
        # Wrap it
        session_wrp = SessionWrapper(session_obj)
        # Publish all objects
        session_wrp.publish_related_objects(self.connection)
        # Announce the session is there
        self.add_managed_object(session_wrp)
        # Announce any session children
        session_wrp.publish_managed_objects()
        # Return the session wrapper back
        return session_wrp

    @dbus.service.method(
        dbus_interface=SERVICE_IFACE, in_signature='oo', out_signature='')
    @PlainBoxObjectWrapper.translate
    def RunJob(self, session: 'o', job: 'o'):
        running_job_wrp = RunningJob(job, session, conn=self.connection)
        self.native.run_job(session, job, running_job_wrp)


class UIOutputPrinter(extcmd.DelegateBase):
    """
    Delegate for extcmd that redirect all output to the UI.
    """

    def __init__(self, runner):
        self._lineno = collections.defaultdict(int)
        self._runner = runner

    def on_line(self, stream_name, line):
        # FIXME: this is not a line number,
        # TODO: tie this into existing code in runner.py (the module)
        self._lineno[stream_name] += 1
        self._runner.IOLogGenerated(self._lineno[stream_name],
                                    stream_name, line)


class RunningJob(dbus.service.Object):
    """
    DBus representation of a running job.
    """

    def __init__(self, job, session, conn=None, object_path=None,
                 bus_name=None):
        if object_path is None:
            object_path = "/plainbox/jobrunner/{}".format(id(self))
        self.path = object_path
        dbus.service.Object.__init__(self, conn, self.path, bus_name)
        self.job = job
        self.session = session
        self.result = {}
        self.ui_io_delegate = UIOutputPrinter(self)

    @dbus.service.method(
        dbus_interface=RUNNING_JOB_IFACE, in_signature='', out_signature='')
    def Kill(self):
        pass

    @dbus.service.property(dbus_interface=RUNNING_JOB_IFACE, signature="s")
    def outcome_from_command(self):
        if self.result.get('return_code') is not None:
            if self.result.get('return_code') == 0:
                return "pass"
            else:
                return "fail"
        else:
            return ""

    @dbus.service.method(
        dbus_interface=RUNNING_JOB_IFACE, in_signature='ss', out_signature='')
    def SetOutcome(self, outcome, comments=None):
        self.result['outcome'] = outcome
        self.result['comments'] = comments
        job_result = DiskJobResult(self.result)
        self.emitJobResultAvailable(self.job, job_result)

    def _command_callback(self, return_code, record_path):
        self.result['return_code'] = return_code
        self.result['io_log_filename'] = record_path
        self.emitAskForOutcomeSignal()

    def _run_command(self, session, job, parent):
        """
        Run a Job command in a separate thread
        """
        ui_io_delegate = UIOutputPrinter(self)
        runner = JobRunner(session.session_dir, session.jobs_io_log_dir,
                           command_io_delegate=ui_io_delegate)
        return_code, record_path = runner._run_command(job, None)
        parent._command_callback(return_code, record_path)

    @dbus.service.method(
        dbus_interface=RUNNING_JOB_IFACE, in_signature='', out_signature='')
    def RunCommand(self):
        # FIXME: this thread object leaks, it needs to be .join()ed
        runner = Thread(target=self._run_command,
                        args=(self.session, self.job, self))
        runner.start()

    @dbus.service.signal(
        dbus_interface=SERVICE_IFACE, signature='dsay')
    def IOLogGenerated(self, offset, name, data):
        pass

    # XXX: Try to use PlainBoxObjectWrapper.translate here instead of calling
    # emitJobResultAvailable to do the translation
    @dbus.service.signal(
        dbus_interface=SERVICE_IFACE, signature='oo')
    def JobResultAvailable(self, job, result):
        pass

    @dbus.service.signal(
        dbus_interface=SERVICE_IFACE, signature='o')
    def AskForOutcome(self, runner):
        pass

    def emitAskForOutcomeSignal(self, *args):
        self.AskForOutcome(self.path)

    def emitJobResultAvailable(self, job, result):
        result_wrapper = JobResultWrapper(result)
        result_wrapper.publish_related_objects(self.connection)
        job_path = PlainBoxObjectWrapper.find_wrapper_by_native(job)
        result_path = PlainBoxObjectWrapper.find_wrapper_by_native(result)
        self.JobResultAvailable(job_path, result_path)

    def update_job_result_callback(self, job, result):
        self.emitJobResultAvailable(job, result)
