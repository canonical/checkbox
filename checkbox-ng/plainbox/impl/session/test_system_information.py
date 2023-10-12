import json
from unittest import TestCase
from subprocess import CalledProcessError
from unittest.mock import MagicMock, patch

from plainbox.impl.session.system_information import (
    Collector,
    OutputSuccess,
    OutputFailure,
    CollectionOutput,
    collect,
)


class TestCollector(TestCase):
    def test_collect_version_success(self):
        self_mock = MagicMock()
        with patch(
            "plainbox.impl.session.system_information.check_output"
        ) as check_output_mock:
            check_output_mock.return_value = "some_version_string"
            version = Collector.collect_version(self_mock)
        # The version field should contain exactly what was produced
        # by the version collection command
        self.assertEqual(version, "some_version_string")

    def test_collect_version_failure(self):
        self_mock = MagicMock()
        with patch(
            "plainbox.impl.session.system_information.check_output"
        ) as check_output_mock:
            check_output_mock.side_effect = CalledProcessError(
                1, "Command failed"
            )
            version = Collector.collect_version(self_mock)
        # Don't crash when version collection fails but report the error
        # in the version info
        self.assertIn("Command failed", version)

    def test_collect_outputs_success(self):
        self_mock = MagicMock()

        collection_result = MagicMock()
        collection_result.returncode = 0
        collection_result.stdout = '{"key": "value"}'

        with patch("plainbox.impl.session.system_information.run") as run_mock:
            run_mock.return_value = collection_result
            outputs, return_code = Collector.collect_outputs(self_mock)
        # The command correctly reports that everything was ok with the
        # system_information, returning OutputSuccess
        self.assertTrue(isinstance(outputs, OutputSuccess))
        # The output has to be in the json field, parsed
        self.assertTrue(outputs.json_output["key"], "value")
        # The return code is stored as is
        self.assertEqual(return_code, 0)

    def test_collect_outputs_failure_command(self):
        self_mock = MagicMock()

        collection_result = MagicMock()
        collection_result.returncode = 1
        collection_result.stderr = "Command failed"
        collection_result.stdout = ""

        with patch("plainbox.impl.session.system_information.run") as run_mock:
            run_mock.return_value = collection_result
            outputs, return_code = Collector.collect_outputs(self_mock)
        # The function detects the failure and reports it by returning
        # OutputFailure
        self.assertTrue(isinstance(outputs, OutputFailure))
        # stdout and stderr are stored as is
        self.assertEqual(outputs.stdout, collection_result.stdout)
        self.assertEqual(outputs.stderr, collection_result.stderr)
        # The return code is stored as is
        self.assertEqual(return_code, 1)

    def test_collect_outputs_failure_json(self):
        self_mock = MagicMock()

        collection_result = MagicMock()
        collection_result.returncode = 0
        collection_result.stdout = "Invalid JSON"

        try:
            json.loads(collection_result.stdout)
            self.fail(
                "{} should be an invalid json".format(collection_result.stdout)
            )
        except json.JSONDecodeError as e:
            exception_str = str(e)

        with patch("plainbox.impl.session.system_information.run") as run_mock:
            run_mock.return_value = collection_result
            outputs, return_code = Collector.collect_outputs(self_mock)
        # The function detects that the output json is invalid
        # and returns OutputFailure
        self.assertTrue(isinstance(outputs, OutputFailure))
        # The stdout is included in the reported stdout along with the
        # parsing problem
        self.assertIn(collection_result.stdout, outputs.stdout)
        self.assertIn(exception_str, outputs.stdout)
        # The return code is stored as is
        self.assertEqual(return_code, 0)

    def test_collect_ok(self):
        collector = Collector(version_cmd=[], collection_cmd=[])
        with patch(
            "plainbox.impl.session.system_information.run"
        ) as run_mock, patch(
            "plainbox.impl.session.system_information.check_output"
        ) as check_output_mock:
            check_output_mock.return_value = "version_str"
            collection_result = MagicMock()
            collection_result.returncode = 0
            collection_result.stdout = '{"key": "value"}'
            run_mock.return_value = collection_result

            collection_output = collector.collect()
            # Correctly report an OutputSuccess as outputs
            self.assertTrue(
                isinstance(collection_output.outputs, OutputSuccess)
            )
            # The version_str is stored as is
            self.assertEqual(collection_output.tool_version, "version_str")
            # The return code is stored as is
            self.assertEqual(collection_output.return_code, 0)

    def test_collect_fail(self):
        collector = Collector(version_cmd=[], collection_cmd=[])
        with patch(
            "plainbox.impl.session.system_information.run"
        ) as run_mock, patch(
            "plainbox.impl.session.system_information.check_output"
        ) as check_output_mock:
            check_output_mock.return_value = "version_str"
            collection_result = MagicMock()
            collection_result.returncode = 1
            collection_result.stdout = '{"key": "value"}'
            run_mock.return_value = collection_result

            collection_output = collector.collect()
            # Correctly report an OutputSuccess as outputs
            self.assertTrue(
                isinstance(collection_output.outputs, OutputFailure)
            )
            # The version_str is stored as is
            self.assertEqual(collection_output.tool_version, "version_str")
            # The return code is stored as is
            self.assertEqual(collection_output.return_code, 1)


class TestCollectionOutput(TestCase):
    def test_to_dict_success(self):
        output_success = OutputSuccess({"key": "value"}, "")
        collection_output = CollectionOutput(
            tool_version="1.0", return_code=0, outputs=output_success
        )
        expected_dict = {
            "tool_version": "1.0",
            "return_code": 0,
            "outputs": output_success.to_dict(),
        }
        self.assertEqual(collection_output.to_dict(), expected_dict)

    def test_to_dict_failure(self):
        output_failure = OutputFailure("Failure", "")
        collection_output = CollectionOutput(
            tool_version="1.0", return_code=1, outputs=output_failure
        )
        expected_dict = {
            "tool_version": "1.0",
            "return_code": 1,
            "outputs": output_failure.to_dict(),
        }
        self.assertEqual(collection_output.to_dict(), expected_dict)

    def test_from_dict_success(self):
        input_dict = {
            "tool_version": "1.0",
            "return_code": 0,
            "outputs": {
                "json_output": {"key": "value"},
                "stderr": "",
                "success": True,
            },
        }
        collection_output = CollectionOutput.from_dict(input_dict)
        self.assertEqual(collection_output.tool_version, "1.0")
        self.assertEqual(collection_output.return_code, 0)
        self.assertTrue(isinstance(collection_output.outputs, OutputSuccess))
        self.assertEqual(
            collection_output.outputs.json_output, {"key": "value"}
        )
        self.assertEqual(collection_output.outputs.stderr, "")
        self.assertTrue(collection_output.outputs.success)

    def test_from_dict_failure(self):
        input_dict = {
            "tool_version": "1.0",
            "return_code": 1,
            "outputs": {"stdout": "Failure", "stderr": "", "success": False},
        }
        collection_output = CollectionOutput.from_dict(input_dict)
        self.assertEqual(collection_output.tool_version, "1.0")
        self.assertEqual(collection_output.return_code, 1)
        self.assertTrue(isinstance(collection_output.outputs, OutputFailure))
        self.assertEqual(collection_output.outputs.stdout, "Failure")
        self.assertEqual(collection_output.outputs.stderr, "")
        self.assertFalse(collection_output.outputs.success)


class TestCollect(TestCase):
    def test_collect(self):
        with patch(
            "plainbox.impl.session.system_information.InxiCollector"
        ) as inxi_collector:
            collect()
        self.assertTrue(inxi_collector.collect.called)
