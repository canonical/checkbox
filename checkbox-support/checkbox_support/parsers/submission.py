#
# This file is part of Checkbox.
#
# Copyright 2011 Canonical Ltd.
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
#

from itertools import product
try:
    import xml.etree.cElementTree as etree
except ImportError:
    import cElementTree as etree

import re

from checkbox_support import parsers
from checkbox_support.parsers.cpuinfo import CpuinfoParser
from checkbox_support.parsers.cputable import CputableParser
from checkbox_support.parsers.dmidecode import DmidecodeParser
from checkbox_support.parsers.efi import EfiParser
from checkbox_support.parsers.meminfo import MeminfoParser
from checkbox_support.parsers.udevadm import UdevadmParser
from io import StringIO
from logging import getLogger
from pkg_resources import resource_string

from checkbox.lib.conversion import string_to_datetime

from checkbox.job import (FAIL, PASS, UNINITIATED, UNRESOLVED,
    UNSUPPORTED, UNTESTED)


# The DeferredParser copied from checkbox-legacy's deffered.py
class DeferredParser:
    """Parser for deferred dispatching of events."""

    def __init__(self, dispatcher, event_type="result"):
        self.dispatcher = dispatcher
        self.event_type = event_type

    def run(self, result):
        self.dispatcher.publishEvent(self.event_type, result)




# All of the dispatcher machinery copied from lp:checkbox-legacy's
# dispatcher.py
class Event:
    """Event payload containing the positional and keywoard arguments
    passed to the handler in the event listener."""

    def __init__(self, type, *args, **kwargs):
        self.type = type
        self.args = args
        self.kwargs = kwargs


class Listener:
    """Event listener notified when events are published by the dispatcher."""

    def __init__(self, event_type, handler, count):
        self.event_type = event_type
        self.handler = handler
        self.count = count

    def notify(self, event):
        """Notify the handler with the payload of the event.

        :param event: The event containint the payload for the handler.
        """
        if self.count is None or self.count:
            self.handler(*event.args, **event.kwargs)
            if self.count:
                self.count -= 1


class ListenerList(Listener):
    """Event listener notified for lists of events."""

    def __init__(self, *args, **kwargs):
        super(ListenerList, self).__init__(*args, **kwargs)
        self.event_types = set(self.event_type)
        self.kwargs = {}

    def notify(self, event):
        """Only notify the handler when all the events for this listener
        have been published by the dispatcher. When duplicate events
        occur, the latest event is preserved and the previous one are
        overwritten until all events have been published.
        """
        if self.count is None or self.count:
            self.kwargs[event.type] = event.args[0]
            if self.event_types.issubset(self.kwargs):
                self.handler(**self.kwargs)
                if self.count:
                    self.count -= 1


class ListenerQueue(ListenerList):

    def notify(self, event):
        """Only notify the handler when all the events for this listener
        have been published by the dispatcher. Duplicate events are enqueued
        and dequeued only when all events have been published.
        """
        arg = event.args[0]
        queue = self.kwargs.setdefault(event.type, [])

        # Strip duplicates from the queue.
        if arg not in queue:
            queue.append(arg)

        # Once the queue has handler has been called, the queue
        # then behaves like a list using the latest events.
        if self.event_types.issubset(self.kwargs):
            self.notify = notify = super(ListenerQueue, self).notify
            keys = list(self.kwargs.keys())
            for values in product(*list(self.kwargs.values())):
                self.kwargs = dict(list(zip(keys, values)))
                notify(event)


class Dispatcher:
    """Register handlers and publish events for them identified by strings."""

    listener_factory = Listener

    def __init__(self, listener_factory=None):
        self._event_listeners = {}

        if listener_factory is not None:
            self.listener_factory = listener_factory

    def registerHandler(self, event_type, handler, count=None):
        """Register an event handler and return its listener.

        :param event_type: The name of the event type to handle.
        :param handler: The function handling the given event type.
        :param count: Optionally, the number times to call the handler.
        """
        listener = self.listener_factory(event_type, handler, count)

        listeners = self._event_listeners.setdefault(event_type, [])
        listeners.append(listener)

        return listener

    def unregisterHandler(self, handler):
        """Unregister a handler.

        :param handler: The handler to unregister.
        """
        for event_type, listeners in self._event_listeners.items():
            listeners = [
                listener for listener in listeners
                if listener.handler == handler]
            if listeners:
                self._event_listeners[event_type] = listeners
            else:
                del self._event_listeners[event_type]

    def unregisterListener(self, listener, event_type=None):
        """Unregister a listener.

        :param listener: The listener of the handler to unregister.
        :param event_type: Optionally, the event_type to unregister.
        """
        if event_type is None:
            event_type = listener.event_type

        self._event_listeners[event_type].remove(listener)
        if not self._event_listeners[event_type]:
            del self._event_listeners[event_type]

    def publishEvent(self, event_type, *args, **kwargs):
        """Publish an event of a given type and notify all listeners.

        :param event_type: The name of the event type to publish.
        :param args: Positional arguments to pass to the registered handlers.
        :param kwargs: Keyword arguments to pass to the registered handlers.
        """
        if event_type in self._event_listeners:
            event = Event(event_type, *args, **kwargs)
            for listener in list(self._event_listeners[event_type]):
                try:
                    listener.notify(event)
                    if listener.count is not None and not listener.count:
                        self.unregisterListener(listener)
                except:
                    logging.exception(
                        "Error running event handler for %r with args %r %r",
                        event_type, args, kwargs)


class DispatcherList(Dispatcher):
    """
    Register handlers and publish events for them identified by lists
    of strings.
    """

    listener_factory = ListenerList

    def registerHandler(self, event_types, handler, count=None):
        """See Dispatcher."""
        if not isinstance(event_types, (list, tuple)):
            event_types = (event_types,)

        listener = self.listener_factory(event_types, handler, count)
        for event_type in event_types:
            listeners = self._event_listeners.setdefault(event_type, [])
            listeners.append(listener)

        return listener

    def unregisterListener(self, listener):
        """See Dispatcher."""
        for event_type in listener.event_types:
            super(DispatcherList, self).unregisterListener(
                listener, event_type)

    def publishEvent(self, event_type, arg):
        """See Dispatcher."""
        super(DispatcherList, self).publishEvent(event_type, arg)


class DispatcherQueue(DispatcherList):
    """
    Register handlers and publish events for them identified by lists
    of strings in queue order.
    """

    listener_factory = ListenerQueue
class SubmissionResult:

    def __init__(self, test_run_factory, **kwargs):
        self.test_run_factory = test_run_factory
        self.test_run_kwargs = kwargs
        self.dispatcher = DispatcherQueue()

        # Register handlers to incrementally add information
        register = self.dispatcher.registerHandler
        register(("cpu", "architecture",), self.addCpuArchitecture)
        register(("identifier",), self.addIdentifier)
        register(("test_run", "attachment",), self.addAttachment)
        register(("test_run", "device",), self.addDeviceState)
        register(("test_run", "dmi_device",), self.addDmiDeviceState)
        register(("test_run", "distribution",), self.setDistribution)
        register(("test_run", "package_version",), self.addPackageVersion)
        register(("test_run", "test_result",), self.addTestResult)

        # Register handlers to set information once
        register(("architecture",), self.setArchitecture, count=1)
        register(
            ("cpuinfo", "machine", "cpuinfo_result",),
            self.setCpuinfo, count=1)
        register(
            ("meminfo", "meminfo_result",),
            self.setMeminfo, count=1)
        register(
            ("project", "series",),
            self.setTestRun, count=1)
        register(
            ("test_run", "architecture",),
            self.setArchitectureState, count=1)
        register(
            ("test_run", "kernel",),
            self.setKernelState, count=1)
        register(
            ("test_run", "memory",),
            self.setMemoryState, count=1)
        register(
            ("test_run", "processor",),
            self.setProcessorState, count=1)
        register(
            ("udevadm", "bits", "udevadm_result",),
            self.setUdevadm, count=1)

        # Publish events passed as keyword arguments
        if "project" in kwargs:
            self.dispatcher.publishEvent("project", kwargs.pop("project"))
            self.dispatcher.publishEvent("series", kwargs.pop("series", None))

    def addAttachment(self, test_run, attachment):
        test_run.addAttachment(**attachment)

    def addContext(self, text, command=None):
        if text.strip() == "Command not found.":
            return

        self.dispatcher.publishEvent(
            "attachment", {"name": command, "content": text})

        context_parsers = {
            "/proc/cpuinfo": self.parseCpuinfo,
            "meminfo": self.parseMeminfo,
            "dmidecode": DmidecodeParser,
            "udevadm": self.parseUdevadm,
            "efi": EfiParser,
            }
        for context, parser in context_parsers.items():
            if context in command:
                if hasattr(text, "decode"):
                    text = text.decode("utf-8")
                stream = StringIO(text)
                p = parser(stream)
                p.run(self)

    def addCpu(self, cpu):
        self.dispatcher.publishEvent("cpu", cpu)

    def addCpuArchitecture(self, cpu, architecture):
        regex = re.compile(cpu['regex'])
        if cpu["debian_name"] == architecture or regex.match(architecture):
            self.dispatcher.publishEvent("machine", cpu["gnu_name"])
            self.dispatcher.publishEvent("bits", cpu["bits"])

    def addDevice(self, device):
        self.dispatcher.publishEvent("device", device)

    def addDeviceState(self, test_run, device):
        test_run.addDeviceState(
            bus_name=device.bus, category_name=device.category,
            product_name=device.product, vendor_name=device.vendor,
            product_id=device.product_id, vendor_id=device.vendor_id,
            subproduct_id=device.subproduct_id,
            subvendor_id=device.subvendor_id,
            driver_name=device.driver, path=device.path)

    def addDmiDevice(self, device):
        if device.serial:
            self.dispatcher.publishEvent("identifier", device.serial)

        if device.category in ("BOARD", "SYSTEM") \
           and device.vendor != device.product \
           and device.product is not None:
            self.dispatcher.publishEvent("model", device.product)
            self.dispatcher.publishEvent("make", device.vendor)
            self.dispatcher.publishEvent("version", device.version)

        if device.category != "DEVICE":
            self.dispatcher.publishEvent("dmi_device", device)

    def addDmiDeviceState(self, test_run, dmi_device):
        test_run.addDeviceState(
            bus_name="dmi", category_name=dmi_device.category,
            product_name=dmi_device.product, vendor_name=dmi_device.vendor,
            product_id=None, vendor_id=None,
            subproduct_id=None, subvendor_id=None,
            driver_name=None, path=dmi_device.path)

    def addIdentifier(self, identifier):
        try:
            self.identifiers.append(identifier)
        except AttributeError:
            self.identifiers = [identifier]
            self.dispatcher.publishEvent("identifiers", self.identifiers)

    def addPackage(self, package):
        package_version = {
            "name": package["name"],
            "version": package["properties"]["version"],
            }
        self.dispatcher.publishEvent("package_version", package_version)

    def addPackageVersion(self, test_run, package_version):
        test_run.addPackageVersion(**package_version)

    def addQuestion(self, question):
        answer_to_status = {
            "fail": FAIL,
            "no": FAIL,
            "pass": PASS,
            "skip": UNTESTED,
            "uninitiated": UNINITIATED,
            "unresolved": UNRESOLVED,
            "unsupported": UNSUPPORTED,
            "untested": UNTESTED,
            "yes": PASS,
            }

        test_result = dict(
            name=question["name"],
            output=question["comment"],
            status=answer_to_status[question["answer"]["value"]],
            )
        test_result.update(self.test_run_kwargs)
        self.dispatcher.publishEvent("test_result", test_result)

    def addTestResult(self, test_run, test_result):
        test_run.addTestResult(**test_result)

    def addSummary(self, name, value):
        if name == "architecture":
            self.dispatcher.publishEvent("architecture", value)
        elif name == "distribution":
            self.dispatcher.publishEvent("project", value)
        elif name == "distroseries":
            self.dispatcher.publishEvent("series", value)
        elif name == "kernel-release":
            self.dispatcher.publishEvent("kernel", value)

    def parseCpuinfo(self, cpuinfo):
        self.dispatcher.publishEvent("cpuinfo", cpuinfo)
        return DeferredParser(self.dispatcher, "cpuinfo_result")

    def parseMeminfo(self, meminfo):
        self.dispatcher.publishEvent("meminfo", meminfo)
        return DeferredParser(self.dispatcher, "meminfo_result")

    def parseUdevadm(self, udevadm):
        self.dispatcher.publishEvent("udevadm", udevadm)
        return DeferredParser(self.dispatcher, "udevadm_result")

    def setArchitecture(self, architecture):
        string = resource_string(parsers.__name__, "cputable")
        stream = StringIO(string.decode("utf-8"))
        parser = CputableParser(stream)
        parser.run(self)

    def setArchitectureState(self, test_run, architecture):
        test_run.setArchitectureState(architecture)

    def setKernelState(self, test_run, kernel):
        test_run.setKernelState(kernel)

    def setCpuinfo(self, cpuinfo, machine, cpuinfo_result):
        parser = CpuinfoParser(cpuinfo, machine)
        parser.run(cpuinfo_result)

    def setEfiDevice(self, device):
        self.dispatcher.publishEvent("dmi_device", device)

    def setMeminfo(self, meminfo, meminfo_result):
        parser = MeminfoParser(meminfo)
        parser.run(meminfo_result)

    def setDistribution(self, test_run, distribution):
        test_run.setDistribution(**distribution)

    def setLSBRelease(self, lsb_release):
        self.dispatcher.publishEvent("distribution", lsb_release)

    def setMemory(self, memory):
        self.dispatcher.publishEvent("memory", memory)

    def setMemoryState(self, test_run, memory):
        test_run.setMemoryState(**memory)

    def setProcessor(self, processor):
        self.dispatcher.publishEvent("processor", processor)

    def setProcessorState(self, test_run, processor):
        test_run.setProcessorState(
            platform_name=processor["platform"],
            make=processor["type"], model=processor["model"],
            model_number=processor["model_number"],
            model_version=processor["model_version"],
            model_revision=processor["model_revision"],
            cache=processor["cache"], other=processor["other"],
            bogomips=processor["bogomips"], speed=processor["speed"],
            count=processor["count"])

    def setTestRun(self, project, series):
        test_run = self.test_run_factory(
            **self.test_run_kwargs)
        self.dispatcher.publishEvent("test_run", test_run)

    def setUdevadm(self, udevadm, bits, udevadm_result):
        parser = UdevadmParser(udevadm, bits)
        parser.run(udevadm_result)


class SubmissionParser:

    def __init__(self, file):
        self.file = file
        self.logger = getLogger()

    def _getClient(self, node):
        """Return a dictionary with the name and version of the client."""
        return {
            "name": node.get("name"),
            "version": node.get("version"),
            }

    def _getProperty(self, node):
        """Return the (name, value) of a property."""
        return (node.get("name"), self._getValueAsType(node))

    def _getProperties(self, node):
        """Return a dictionary of properties."""
        properties = {}
        for child in node.getchildren():
            assert child.tag == "property", \
                "Unexpected tag <%s>, expected <property>" % child.tag
            name, value = self._getProperty(child)
            properties[name] = value

        return properties

    def _getValueAsType(self, node):
        """Return value of a node as the type attribute."""
        type_ = node.get("type")
        if type_ in ("bool",):
            value = node.text.strip()
            assert value in ("True", "False",), \
                "Unexpected boolean value '%s' in <%s>" % (value, node.tag)
            return value == "True"
        elif type_ in ("str",):
            return str(node.text.strip())
        elif type_ in ("int", "long",):
            return int(node.text.strip())
        elif type_ in ("float",):
            return float(node.text.strip())
        elif type_ in ("list",):
            return list(self._getValueAsType(child)
                for child in node.getchildren())
        elif type_ in ("dict",):
            return dict((child.get("name"), self._getValueAsType(child))
                for child in node.getchildren())
        else:
            raise AssertionError(
                "Unexpected type '%s' in <%s>" % (type_, node.tag))

    def _getValueAsBoolean(self, node):
        """Return the value of the attribute "value" as a boolean."""
        value = node.attrib["value"]
        assert value in ("True", "False",), \
            "Unexpected boolean value '%s' in tag <%s>" % (value, node.tag)
        return value == "True"

    def _getValueAsDatetime(self, node):
        """Return the value of the attribute "value" as a datetime."""
        string = node.attrib["value"]
        return string_to_datetime(string)

    def _getValueAsString(self, node):
        """Return the value of the attribute "value"."""
        return str(node.attrib["value"])

    def parseContext(self, result, node):
        """Parse the <context> part of a submission."""
        duplicates = set()
        for child in node.getchildren():
            assert child.tag == "info", \
                "Unexpected tag <%s>, expected <info>" % child.tag
            command = child.get("command")
            if command not in duplicates:
                duplicates.add(command)
                text = child.text
                if text is None:
                    text = ""
                result.addContext(text, command)
            else:
                self.logger.debug(
                    "Duplicate command found in tag <info>: %s" % command)

    def parseHardware(self, result, node):
        """Parse the <hardware> section of a submission."""
        parsers = {
            "dmi": DmidecodeParser,
            "processors": self.parseProcessors,
            "udev": result.parseUdevadm,
            }

        for child in node.getchildren():
            parser = parsers.get(child.tag)
            if parser:
                if child.getchildren():
                    parser(result, child)
                else:
                    text = child.text
                    if hasattr(text, "decode"):
                        text = text.decode("utf-8")
                    stream = StringIO(text)
                    p = parser(stream)
                    p.run(result)
            else:
                self.logger.debug(
                    "Unsupported tag <%s> in <hardware>" % child.tag)

    def parseLSBRelease(self, result, node):
        """Parse the <lsbrelease> part of a submission."""
        properties = self._getProperties(node)
        result.setLSBRelease(properties)

    def parsePackages(self, result, node):
        """Parse the <packages> part of a submission."""
        for child in node.getchildren():
            assert child.tag == "package", \
                "Unexpected tag <%s>, expected <package>" % child.tag

            package = {
                "name": child.get("name"),
                "properties": self._getProperties(child),
                }
            result.addPackage(package)

    def parseProcessors(self, result, node):
        """Parse the <processors> part of a submission."""
        processors = []
        for child in node.getchildren():
            assert child.tag == "processor", \
                "Unexpected tag <%s>, expected <processor>" % child.tag

            # Convert lists to space separated strings.
            properties = self._getProperties(child)
            for key, value in properties.items():
                if key in ("bogomips", "cache", "count", "speed",):
                    properties[key] = int(float(value))
                elif isinstance(value, list):
                    properties[key] = " ".join(value)
            processors.append(properties)

        # Check if /proc/cpuinfo was parsed already.
        if any("platform" in processor for processor in processors):
            result.setProcessor(processors[0])
        else:
            lines = []
            for processor in processors:
                # Convert some keys with underscores to spaces instead.
                for key, value in processor.items():
                    if "_" in key and key != "vendor_id":
                        key = key.replace("_", " ")

                    lines.append("%s: %s" % (key, value))

                lines.append("")

            if lines:
                if hasattr(lines[0], "decode"):
                    lines = [line.decode("utf-8") for line in lines]
                stream = StringIO("\n".join(lines))
                parser = result.parseCpuinfo(stream)
                parser.run(result)

    def parseQuestions(self, result, node):
        """Parse the <questions> part of a submission."""
        for child in node.getchildren():
            assert child.tag == "question", \
                "Unexpected tag <%s>, expected <question>" % child.tag
            question = {
                "name": child.get("name"),
                "targets": [],
                }
            plugin = child.get("plugin", None)
            if plugin is not None:
                question["plugin"] = plugin

            answer_choices = []
            for sub_node in child.getchildren():
                sub_tag = sub_node.tag
                if sub_tag == "answer":
                    question["answer"] = answer = {}
                    answer["type"] = sub_node.get("type")
                    if answer["type"] == "multiple_choice":
                        question["answer_choices"] = answer_choices
                    unit = sub_node.get("unit", None)
                    if unit is not None:
                        answer["unit"] = unit
                    answer["value"] = sub_node.text.strip()

                elif sub_tag == "answer_choices":
                    for value_node in sub_node.getchildren():
                        answer_choices.append(
                            self._getValueAsType(value_node))

                elif sub_tag == "target":
                    # The Relax NG schema ensures that the attribute
                    # id exists and that it is an integer
                    target = {"id": int(sub_node.get("id"))}
                    target["drivers"] = drivers = []
                    for driver_node in sub_node.getchildren():
                        drivers.append(driver_node.text.strip())
                    question["targets"].append(target)

                elif sub_tag in ("comment", "command",):
                    text = sub_node.text
                    if text is None:
                        text = ""
                    question[sub_tag] = text.strip()

                else:
                    raise AssertionError(
                        "Unexpected tag <%s> in <question>" % sub_tag)

            result.addQuestion(question)

    def parseSoftware(self, result, node):
        """Parse the <software> section of a submission."""
        parsers = {
            "lsbrelease": self.parseLSBRelease,
            "packages": self.parsePackages,
            }

        for child in node.getchildren():
            parser = parsers.get(child.tag)
            if parser:
                parser(result, child)
            else:
                self.logger.debug(
                    "Unsupported tag <%s> in <software>" % child.tag)

    def parseSummary(self, result, node):
        """Parse the <summary> section of a submission."""
        parsers = {
            "architecture": self._getValueAsString,
            "client": self._getClient,
            "contactable": self._getValueAsBoolean,
            "date_created": self._getValueAsDatetime,
            "distribution": self._getValueAsString,
            "distroseries": self._getValueAsString,
            "kernel-release": self._getValueAsString,
            "live_cd": self._getValueAsBoolean,
            "private": self._getValueAsBoolean,
            "system_id": self._getValueAsString,
            }

        for child in node.getchildren():
            parser = parsers.get(child.tag)
            if parser:
                value = parser(child)
                result.addSummary(child.tag, value)
            else:
                self.logger.debug(
                    "Unsupported tag <%s> in <summary>" % child.tag)

    def parseRoot(self, result, node):
        """Parse the <system> root of a submission."""
        parsers = {
            "context": self.parseContext,
            "hardware": self.parseHardware,
            "questions": self.parseQuestions,
            "software": self.parseSoftware,
            "summary": self.parseSummary,
            }

        # Iterate over the root children, "summary" first
        for child in node.getchildren():
            parser = parsers.get(child.tag)
            if parser:
                parser(result, child)
            else:
                self.logger.debug(
                    "Unsupported tag <%s> in <system>" % child.tag)

    def run(self, test_run_factory, **kwargs):
        parser = etree.XMLParser()

        tree = etree.parse(self.file, parser=parser)
        root = tree.getroot()
        if root.tag != "system":
            raise AssertionError(
                "Unexpected tag <%s> at root, expected <system>" % root.tag)

        result = SubmissionResult(test_run_factory, **kwargs)
        self.parseRoot(result, root)

        return result
