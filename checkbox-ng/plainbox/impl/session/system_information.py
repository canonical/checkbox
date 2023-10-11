import json
from subprocess import run, PIPE, check_output, STDOUT, CalledProcessError

from plainbox.vendor import system_information


class OutputSuccess:
    def __init__(self, json_output: dict, stderr: str):
        self.json_output = json_output
        self.stderr = stderr
        self.success = True

    def to_dict(self):
        return {
            "json_output": self.json_output,
            "stderr": self.stderr,
            "success": self.success,
        }

    @classmethod
    def from_dict(cls, dct):
        return cls(dct["json_output"], dct["stderr"])


class OutputFailure:
    def __init__(self, stdout: str, stderr: str):
        self.stdout = stdout
        self.stderr = stderr
        self.success = False

    def to_dict(self):
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "success": self.success,
        }

    @classmethod
    def from_dict(cls, dct):
        return cls(dct["stdout"], dct["stderr"])


class CollectionOutput:
    def __init__(
        self,
        tool_version: str,
        return_code: int,
        outputs: "OutputSuccess|OutputFailure",
    ):
        self.tool_version = tool_version
        self.return_code = return_code
        self.outputs = outputs

    def to_dict(self):
        return {
            "tool_version": self.tool_version,
            "return_code": self.return_code,
            "outputs": self.outputs.to_dict(),
        }

    @classmethod
    def from_dict(cls, dct):
        if dct["outputs"]["success"]:
            outputs = OutputSuccess.from_dict(dct["outputs"])
        else:
            outputs = OutputFailure.from_dict(dct["outputs"])
        return cls(dct["tool_version"], dct["return_code"], outputs)


class Collector:
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

    def collect_outputs(self) -> "(OutputSuccess|OutputFailure, int)":
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
                    stdout=output, stderr=collection_result.stderr
                )
        return (outputs, collection_result.returncode)

    def collect(self) -> CollectionOutput:
        version_str = self.collect_version()
        outputs, return_code = self.collect_outputs()

        return CollectionOutput(
            tool_version=version_str, return_code=return_code, outputs=outputs
        )


InxiCollector = Collector(
    collection_cmd=[
        system_information.INXI_PATH,
        "--admin",
        "--tty",
        "-v8",
        "--output",
        "json",
        "--output-file",
        "print",
        "-c0",
    ],
    version_cmd=[system_information.INXI_PATH, "--vs"],
)


def collect():
    collectors = {
        "inxi": InxiCollector,
    }
    return {
        name: collector.collect() for (name, collector) in collectors.items()
    }
