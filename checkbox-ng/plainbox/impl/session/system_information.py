#!/usr/bin/env python3

import abc
import json
from subprocess import run, PIPE, check_output, STDOUT, CalledProcessError

from plainbox import vendor


class CollectorOutputs(dict):
    """
    This is the output of all collection. This class is a map
        collector_name : collection_output (see below)
    Once encoded into json it will contain all the items and also
    a "version" key. This version indicates the keys that the
    collector will include in its output
    """

    COLLECTOR_OUTPUTS_VERSION = 1

    def to_json(self) -> str:
        to_dump = {
            name: collected.to_dict() for (name, collected) in self.items()
        }
        to_dump["version"] = self.COLLECTOR_OUTPUTS_VERSION
        return json.dumps(to_dump, indent=4)


class CollectorMeta(type):
    """
    Creates an instance of a Collector type storing what was created
    if it has a COLLECTOR_NAME attribute. The purpose of this is
    centralizing the collection of collectors with this mechanism so
    that whenever a new collector is created the list of them doesn't
    need to be manually updated.

    To subscribe a new Collector simply use this class as the metaclass
    and give it a COLLECTOR_NAME:

        >>> class WillSubscribe(metaclass=CollectorMeta):
        >>>     COLLECTOR_NAME="will_subscribe"

    If you want to create a base collector that will not be subscribed
    here, for example because it needs to be specialized, simply omit the
    COLLECTOR_NAME:

        >>> class WillNotSubscribe(metaclass=CollectorMeta): ...
        >>> class WillSubscribe(WillNotSubscribe):
        >>>     COLLECTOR_NAME = "will_subscribe"
    """

    collectors = {}

    def __new__(cls, clsname, bases, attrs):
        collector_type = super().__new__(cls, clsname, bases, attrs)
        name = attrs.get("COLLECTOR_NAME")
        if name and name in cls.collectors:
            raise ValueError(
                (
                    "Failed to register class '{class_name}' as '{name}'. "
                    "Name is taken by class '{other_class_name}'"
                ).format(
                    name=name,
                    class_name=clsname,
                    other_class_name=cls.collectors[name].__name__,
                )
            )
        if name:
            cls.collectors[name] = collector_type
        return collector_type

    @classmethod
    def collect(cls) -> CollectorOutputs:
        return CollectorOutputs(
            {
                name: collector().collect()
                for (name, collector) in cls.collectors.items()
            }
        )


def collect() -> dict:
    return CollectorMeta.collect()


class OutputABC:
    @abc.abstractmethod
    def to_dict(self):
        """
        Creates a dictionary from the class
        """
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def from_dict(cls, dct) -> "OutputABC":
        """
        Creates this class from a dictionary
        """
        raise NotImplementedError


class OutputSuccess(OutputABC):
    def __init__(self, payload: dict, stderr: str):
        self.payload = payload
        self.stderr = stderr

    def to_dict(self):
        return {
            "payload": self.payload,
            "stderr": self.stderr,
        }

    @classmethod
    def from_dict(cls, dct):
        return cls(dct["payload"], dct["stderr"])


class OutputFailure(OutputABC):
    def __init__(self, stdout: str, stderr: str, return_code: int):
        self.stdout = stdout
        self.stderr = stderr
        self.return_code = return_code

    def to_dict(self):
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "return_code": self.return_code,
        }

    @classmethod
    def from_dict(cls, dct):
        return cls(dct["stdout"], dct["stderr"], dct["return_code"])


class CollectionOutput:
    def __init__(
        self,
        tool_version: str,
        outputs: "OutputABC",
    ):
        self.tool_version = tool_version
        self.outputs = outputs

    @property
    def success(self):
        return isinstance(self.outputs, OutputSuccess)

    def to_dict(self):
        return {
            "tool_version": self.tool_version,
            "success": self.success,
            "outputs": self.outputs.to_dict(),
        }

    @classmethod
    def from_dict(cls, dct):
        if dct["success"]:
            outputs = OutputSuccess.from_dict(dct["outputs"])
        else:
            outputs = OutputFailure.from_dict(dct["outputs"])
        return cls(dct["tool_version"], outputs)


class Collector(metaclass=CollectorMeta):
    def __init__(self, collection_cmd: list, version_cmd: list):
        self.collection_cmd = collection_cmd
        self.version_cmd = version_cmd

    def collect_version(self) -> str:
        """
        Runs the version_cmd returning its output

        :returns: the version fetched form the version_cmd if it runs
                  succesfully
        :returns: a failure message with the exception as a postfix if
                  version_cmd fails
        """
        try:
            return check_output(
                self.version_cmd,
                universal_newlines=True,
                stderr=STDOUT,
            )
        except CalledProcessError as e:
            return "Failed to collect with error: {}".format(e)

    def collect_outputs(self) -> "(OutputSuccess|OutputFailure)":
        """
        Runs the collection_cmd and creates an output.

        :returns: (OutputSuccess, 0) if the command returns 0 and the output
                  is json parsable
        :returns: (OutputFailure, N) if the command returns (N != 0) or the
                  output is not json parsable
        """
        collection_result = run(
            self.collection_cmd,
            universal_newlines=True,
            stdout=PIPE,
            stderr=PIPE,
        )
        if collection_result.returncode != 0:
            outputs = OutputFailure(
                stdout=collection_result.stdout,
                stderr=collection_result.stderr,
                return_code=collection_result.returncode,
            )
        else:
            try:
                json_out = json.loads(collection_result.stdout)
                outputs = OutputSuccess(
                    json_out,
                    stderr=collection_result.stderr,
                )
            except json.JSONDecodeError as e:
                output = (
                    "Failed to decode with error: {}\n"
                    "Collection output:\n{}"
                ).format(str(e), collection_result.stdout)
                outputs = OutputFailure(
                    stdout=output,
                    stderr=collection_result.stderr,
                    return_code=0,
                )
        return outputs

    def collect(self) -> CollectionOutput:
        version_str = self.collect_version()
        outputs = self.collect_outputs()

        return CollectionOutput(tool_version=version_str, outputs=outputs)


class InxiCollector(Collector):
    COLLECTOR_NAME = "inxi"

    def __init__(self):
        super().__init__(
            collection_cmd=[
                str(vendor.INXI_PATH),
                "--admin",
                "--tty",
                "-v8",
                "--output",
                "json",
                "--output-file",
                "print",
                "-c0",
            ],
            version_cmd=[str(vendor.INXI_PATH), "--vs"],
        )


if __name__ == "__main__":
    collection = collect()
    print(collection.to_json())
