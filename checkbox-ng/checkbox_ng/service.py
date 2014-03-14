# This file is part of Checkbox.
#
# Copyright 2013, 2014 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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

"""
:mod:`checkbox_ng.service` -- DBus service for CheckBox
=======================================================
"""

from threading import Lock
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
from plainbox.abc import IJobResult
from plainbox.impl.job import JobDefinition
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.secure.qualifiers import select_jobs
from plainbox.impl.session import JobState
from plainbox.impl.signal import remove_signals_listeners
from plainbox.vendor import extcmd

from checkbox_ng import dbus_ex as dbus
from checkbox_ng.dbus_ex import OBJECT_MANAGER_IFACE
from checkbox_ng.dbus_ex import mangle_object_path

logger = logging.getLogger("checkbox.ng.service")

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
        logger.debug("Created DBus wrapper %s for: %r", id(self), self.native)
        self.__shared_initialize__(**kwargs)

    def __del__(self):
        logger.debug("DBus wrapper %s died", id(self))

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
            if isinstance(obj, PlainBoxObjectWrapper):
                cls._logger.warning(
                    "Application error: %r should have returned native object"
                    " but returned wrapper instead", func)
                return obj
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
        self._checksum = self.native.checksum
        self._is_generated = False

    def _get_preferred_object_path(self):
        # TODO: this clashes with providers, maybe use a random ID instead
        return "/plainbox/job/{}".format(self._checksum)

    # PlainBox properties

    @dbus.service.property(dbus_interface=JOB_IFACE, signature="s")
    def name(self):
        # XXX: name should be removed but for now it should just return the
        # full id instead of the old name (name may be very well gone)
        return self.native.id

    @dbus.service.property(dbus_interface=JOB_IFACE, signature="s")
    def id(self):
        return self.native.id

    @dbus.service.property(dbus_interface=JOB_IFACE, signature="s")
    def partial_id(self):
        return self.native.partial_id

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
                str(self.native.origin.source),
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
            mangle_object_path(self.native.name))

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
        super(JobResultWrapper, self).__del__()
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
        super(JobStateWrapper, self).__del__()
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
        logger.debug("_result_changed(%r, %r)", old, new)
        # Add the new result object
        try:
            result_wrapper = self.find_wrapper_by_native(new)
        except KeyError:
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
             (inhibitor.related_job.id
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
        self.native.on_job_removed.connect(self._job_removed)

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
        # Mark this job as generated, so far we only add generated jobs at
        # runtime and we need to treat those differently when we're changing
        # the session.
        job_wrapper._is_generated = True
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
        :returns:
            The wrapper for the job that was added

        Take a JobState, wrap it in JobStateWrapper, publish it so that it
        shows up on DBus, add it to the collection of objects managed by this
        SessionWrapper so that it sends InterfacesAdded signals and can be
        enumerated with GetManagedObjects.

        .. note::
            This method must be called after both result and job definition
            have been added (presumably with :meth:`add_job()`
            and :meth:`add_result()`). This method *does not* publish those
            objects, it only publishes the state object.
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
        state = self.native.job_state_map[job.id]
        result = state.result
        assert job is state.job
        # Wrap them in the right order (state has to be last)
        self.add_job(job)
        self.add_result(result)
        state_wrapper = self.add_state(state)
        # Update the job_state_map wrapper that we have here
        self._job_state_map_wrapper[job.id] = state_wrapper
        # Send the signal that the 'job_state_map' property has changed
        self.PropertiesChanged(SESSION_IFACE, {
            self.__class__.job_state_map._dbus_property:
            self._job_state_map_wrapper
        }, [])

    def _job_removed(self, job):
        """
        Internal method connected to the SessionState.on_job_removed() signal.

        This method is called (so far) only when the list of jobs is trimmed
        after doing calling :meth:`Resume()`. This method looks up the
        associated state and result object and removes them. If the removed job
        was not a part of the provider set (it was a generated job) it is also
        removed. Lastly this method sends the appropriate notifications.
        """
        logger.debug("_job_removed(%r)", job)
        # Get references to the three key objects, job, state and result
        state_wrapper = self._job_state_map_wrapper[job.id]
        result_wrapper = state_wrapper._result_wrapper
        job_wrapper = state_wrapper._job_wrapper
        # Remove result and state from our managed object list
        self.remove_managed_object(result_wrapper)
        self.remove_managed_object(state_wrapper)
        # Remove job from managed object list if it was generated
        if job_wrapper._is_generated:
            self.remove_managed_object(job_wrapper)
        # Remove result and state wrappers from dbus
        result_wrapper.remove_from_connection()
        state_wrapper.remove_from_connection()
        # Remove job from dbus if it was generated
        if job_wrapper._is_generated:
            job_wrapper.remove_from_connection()
        # Update the job_state_map wrapper that we have here
        del self._job_state_map_wrapper[job.id]
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
        logger.info("UpdateJobResult(%r, %r)", job, result)
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
        # TODO: this method makes no sense here, it should not be on a session
        # object, it should, if anything, be on the service object.
        logger.info("PreviousSessionFile()")
        previous_session_file = self.native.previous_session_file()
        logger.info("PreviousSessionFile() -> %r", previous_session_file)
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
        logger.info("Clean()")
        self.native.clean()

    @dbus.service.method(
        dbus_interface=SESSION_IFACE, in_signature='', out_signature='')
    def Remove(self):
        logger.info("Remove()")
        # Disconnect all signals listeners from the native session object
        remove_signals_listeners(self)
        for wrapper in self.managed_objects:
            wrapper.remove_from_connection()
        self.remove_from_connection()
        self.native.remove()
        logger.debug("Remove() completed")

    @dbus.service.method(
        dbus_interface=SESSION_IFACE, in_signature='', out_signature='')
    def PersistentSave(self):
        logger.info("PersistentSave()")
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
        self.native.metadata.app_blob = bytes(value.get('app_blob', b''))

    # TODO: signal<metadata>

    @dbus.service.signal(
        dbus_interface=SESSION_IFACE, signature='os')
    def AskForOutcome(self, primed_job: 'o', suggested_outcome: 's'):
        """
        Signal sent when the user should be consulted for the outcome.

        The signal carries:
        - the primed_job instance (which is the sender of this signal anyway).
        - the suggested_outcome for the test based on the execution of the
          test command if it exists.

        This signal triggers important interactions in the GUI, the typical
        use case for the suggested_outcome is:

        - When the "test" button is clicked on a manual test, the outcome
          (e.g. the yes/no/skip radiobox) needs to be automatically updated to
          reflect actual test result. Otherwise, a failing test will not be
          detected by the user, which will cause embarrassment.
        """
        logger.info("AskForOutcome(%r) suggested outcome is (%s)", primed_job,
                    suggested_outcome)

    @dbus.service.signal(
        dbus_interface=SESSION_IFACE, signature='o')
    def ShowInteractiveUI(self, primed_job: 'o'):
        """
        Signal sent when the test requires user interaction.

        The signal carries:
        - the primed_job instance (which is the sender of this signal anyway).

        This signal triggers important interactions in the GUI.
        """
        logger.info("ShowInteractiveUI(%r)", primed_job)


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
        mangled_name = mangle_object_path(self.native.name)
        return "/plainbox/provider/{}".format(mangled_name)

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

    @dbus.service.property(dbus_interface=PROVIDER_IFACE, signature="s")
    def gettext_domain(self):
        """
        the name of the gettext domain associated with this provider

        This value may be empty, in such case provider data cannot be localized
        for the user environment.
        """
        return self.native.gettext_domain or ""


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
        logger.info("Exit()")
        self.native.close()
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
        logger.info("CreateSession(%r)", job_list)
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
        dbus_interface=SERVICE_IFACE, in_signature='oo', out_signature='o')
    @PlainBoxObjectWrapper.translate
    def PrimeJob(self, session: 'o', job: 'o') -> 'o':
        logger.info("PrimeJob(%r, %r)", session, job)
        # Get a primed job for the arguments we've got...
        primed_job = self.native.prime_job(session, job)
        # ...wrap it for DBus...
        primed_job_wrapper = PrimedJobWrapper(
            primed_job, session_wrapper=self.find_wrapper_by_native(session))
        # ...publish it...
        primed_job_wrapper.publish_self(self.connection)
        # Call the method that decides on what to really do, see the docstring
        # for details. This cannot be called inside __init__() as we need to
        # publish the wrapper first. When that happens this method can safely
        # send signals.
        primed_job_wrapper._decide_on_what_to_do()
        # ...and return it
        return primed_job

    RunJob = PrimeJob

    @dbus.service.method(
        dbus_interface=SERVICE_IFACE, in_signature='ao', out_signature='ao')
    @PlainBoxObjectWrapper.translate
    def SelectJobs(self, whitelist_list: 'ao') -> 'ao':
        """
        Compute the effective desired job list out of a list of (arbitrary)
        desired whitelists or job definitions.

        :param whitelist_list:
            A list of jobs or whitelists to select. Each whitelist selects all
            the jobs selected by that whitelist.

            This argument is a simple, limited, encoding of job qualifiers that
            is sufficient to implement the desired semantics of the Checkbox
            GUI.

        :returns:
            A list of jobs that were selected.
        """
        job_list = list(
            itertools.chain(*[
                p.load_all_jobs()[0] for p in self.native.provider_list]))
        return select_jobs(job_list, whitelist_list)


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


class PrimedJobWrapper(PlainBoxObjectWrapper):
    """
    Wrapper for exposing PrimedJob objects on DBus
    """

    HIDDEN_INTERFACES = frozenset(
        OBJECT_MANAGER_IFACE,
    )

    def __shared_initialize__(self, session_wrapper, **kwargs):
        # SessionWrapper instance, we're using it to publish/unpublish results
        # on DBus as they technically belong to the session.
        self._session_wrapper = session_wrapper
        # A result object we got from running the command OR the result this
        # job used to have before. It should be always published on the bus.
        self._result = None
        # A future for the result each time we're waiting for the command to
        # finish. Gets reset to None after the command is done executing.
        self._result_future = None
        # A lock that protects access to :ivar:`_result` and
        # :ivar:`_result_future` from concurrent access from the thread that is
        # executing Future callback which we register, the
        # :meth:`_result_ready()`
        self._result_lock = Lock()

    @dbus.service.method(
        dbus_interface=RUNNING_JOB_IFACE, in_signature='', out_signature='')
    def Kill(self):
        """
        Unused method.

        Could be used to implement a way to cancel the command.
        """
        # NOTE: this should:
        # 1) attempt to cancel the future in the extremely rare case where it
        #    is not started yet
        # 2) kill the job otherwise
        logger.error("Kill() is not implemented")

    @dbus.service.method(
        dbus_interface=RUNNING_JOB_IFACE, in_signature='', out_signature='')
    def RunCommand(self):
        """
        Method invoked by the GUI each time the "test" button is pressed.

        Two cases are possible here:

        1) The command isn't running. In this case we start the command and
           return. A callback will interpret the result once the command
           finishes executing (see :meth:`_legacy_result_juggle()`)

        2) The command is running. In that case we just ignore the call and log
           a warning. The GUI should not make the "test" button clickable while
           the command is runninig.
        """
        if self.native.job.automated:
            logger.error(
                "RunCommand() should not be called for automated jobs")
        with self._result_lock:
            if self._result_future is None:
                logger.info("RunCommand() is starting to run the job")
                self._result_future = self._run_and_set_callback()
            else:
                logger.warning(
                    "RunCommand() ignored, waiting for command to finish")

    # Legacy GUI behavior method.
    # Should be redesigned when we can change GUI internals
    @dbus.service.method(
        dbus_interface=RUNNING_JOB_IFACE, in_signature='ss', out_signature='')
    def SetOutcome(self, outcome, comments=None):
        """
        Method called by the GUI when the "continue" button is pressed.

        Three cases are possible:
        1) There is no result yet
        2) There is a result already
        3) The command is still running! (not handled)
        """
        logger.info("SetOutcome(%r, %r)", outcome, comments)
        with self._result_lock:
            if self._result_future is not None:
                logger.error(
                    "SetOutcome() called while the command is still running!")
            if self._result is None:
                # Warn us if this method is being called on jobs other than
                # 'manual' before we get the result after running RunCommand()
                if self.native.job.plugin != "manual":
                    logger.warning("SetOutcome() called before RunCommand()")
                    logger.warning("But the job is not manual, it is %s",
                                   self.native.job.plugin)
                # Create a new result object
                self._result = MemoryJobResult({
                    'outcome': outcome,
                    'comments': comments
                })
                # Add the new result object to the bus
                self._session_wrapper.add_result(self._result)
            else:
                # Set the values as requested
                self._result.outcome = outcome
                self._result.comments = comments
            # Notify the application that the result is ready. This has to be
            # done unconditionally each time this method called.
            self.JobResultAvailable(
                self.find_wrapper_by_native(self.native.job),
                self.find_wrapper_by_native(self._result))

    # Legacy GUI behavior signal.
    # Should be redesigned when we can change GUI internals
    @dbus.service.property(dbus_interface=RUNNING_JOB_IFACE, signature="s")
    def outcome_from_command(self):
        """
        property that contains the 'outcome' of the result.
        """
        with self._result_lock:
            if self._result is not None:
                # TODO: make it so that we don't have to do this translation
                if self._result.outcome == IJobResult.OUTCOME_NONE:
                    return "none"
                else:
                    return self._result.outcome
            else:
                logger.warning("outcome_from_command() called too early!")
                logger.warning("There is nothing to return yet")
                return ""

    @dbus.service.signal(
        dbus_interface=SERVICE_IFACE, signature='dsay')
    def IOLogGenerated(self, delay, stream_name, data):
        """
        Signal sent when IOLogRecord is generated

        ..note::
            This is not called at all in this implementation.
        """
        logger.info("IOLogGenerated(%r, %r, %r)", delay, stream_name, data)

    # Legacy GUI behavior signal.
    # Should be redesigned when we can change GUI internals
    @dbus.service.signal(
        dbus_interface=SERVICE_IFACE, signature='oo')
    def JobResultAvailable(self, job: 'o', result: 'o'):
        """
        Signal sent when result of running a job is ready
        """
        logger.info("JobResultAvailable(%r, %r)", job, result)

    def _decide_on_what_to_do(self):
        """
        Internal method of PrimedJobWrapper.

        This methods decides on how to behave after we get initialized

        This is a bit of a SNAFU... :/

        The GUI runs jobs differently, depending on the 'plugin' value.
        It either expects to call Service.RunJob() and see the job running
        (so waiting for signals when it is done) or it calls Service.RunJob()
        *and* runs RunCommand() on the returned object (possibly many times).
        """
        # TODO: change this to depend on jobbox 'startup' property
        # http://jobbox.readthedocs.org/en/latest/jobspec.html#startup
        if self.native.job.startup_user_interaction_required:
            logger.info(
                "Sending ShowInteractiveUI() and not starting the job...")
            # Ask the application to show the interaction GUI
            self._session_wrapper.ShowInteractiveUI(self)
        else:
            logger.info("Running %r right away", self.native.job)
            with self._result_lock:
                self._result_future = self._run_and_set_callback()

    def _run_and_set_callback(self):
        """
        Internal method of PrimedJobWrapper

        Starts the future for the job result, adds a callbacks to it and
        returns the future.
        """
        future = self.native.run()
        future.add_done_callback(self._result_ready)
        return future

    def _result_ready(self, result_future):
        """
        Internal method called when the result future becomes ready
        """
        logger.debug("_result_ready(%r)", result_future)
        with self._result_lock:
            if self._result is not None:
                # NOTE: I'm not sure how this would behave if someone were to
                # already assign the old result to any state objects.
                self._session_wrapper.remove_result(self._result)
            # Unpack the result from the future
            self._result = result_future.result()
            # Add the new result object to the session wrapper (and to the bus)
            self._session_wrapper.add_result(self._result)
            # Reset the future so that RunCommand() can run the job again
            self._result_future = None
            # Now fiddle with the GUI notifications
            if self._result.outcome != IJobResult.OUTCOME_UNDECIDED:
                # NOTE: OUTCOME_UNDECIDED is never handled by this method as
                # the user should already see the manual test interaction
                # dialog on their screen. For all other cases we need to notify
                # the GUI that execution has finished and we are really just
                # done with testing.
                logger.debug(
                    "calling JobResultAvailable(%r, %r)",
                    self.native.job, self._result)
                self.JobResultAvailable(
                    self.find_wrapper_by_native(self.native.job),
                    self.find_wrapper_by_native(self._result))
            else:
                logger.debug(
                    ("sending AskForOutcome() after job finished"
                     " running with OUTCOME_UNDECIDED"))
                # Convert the return of the command to the suggested_outcome
                # for the job
                if self._result.return_code == 0:
                    suggested_outcome = IJobResult.OUTCOME_PASS
                else:
                    suggested_outcome = IJobResult.OUTCOME_FAIL
                self._session_wrapper.AskForOutcome(self, suggested_outcome)
