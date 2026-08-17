#!/usr/bin/env python3

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT_DIR = os.path.dirname(__file__)
BIN_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "bin"))
if BIN_DIR not in sys.path:
    sys.path.insert(0, BIN_DIR)

import general_utils


class TestLoadJsonFile(unittest.TestCase):
    def test_load_json_file_reads_relative_path_from_provider_data(self):
        with tempfile.TemporaryDirectory() as provider_dir:
            rel_path = "validation/config.json"
            full_dir = os.path.join(provider_dir, "validation")
            os.makedirs(full_dir, exist_ok=True)
            full_path = os.path.join(full_dir, "config.json")
            payload = {"result": "from-provider"}

            with open(full_path, "w", encoding="utf-8") as file_obj:
                json.dump(payload, file_obj)

            with patch.dict(
                os.environ,
                {"PLAINBOX_PROVIDER_DATA": provider_dir},
                clear=False,
            ):
                data = general_utils.load_json_file(rel_path)

            self.assertEqual(data, payload)

    def test_load_json_file_reads_absolute_path_even_with_provider_data(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            abs_path = os.path.join(tmp_dir, "config.json")
            payload = {"result": "absolute-path"}

            with open(abs_path, "w", encoding="utf-8") as file_obj:
                json.dump(payload, file_obj)

            with patch.dict(
                os.environ,
                {"PLAINBOX_PROVIDER_DATA": "/tmp/provider"},
                clear=False,
            ):
                data = general_utils.load_json_file(abs_path)

            self.assertEqual(data, payload)

    def test_load_json_file_returns_empty_dict_when_file_missing(self):
        with patch.dict(
            os.environ, {"PLAINBOX_PROVIDER_DATA": ""}, clear=False
        ):
            data = general_utils.load_json_file("missing-file.json")

        self.assertEqual(data, {})

    def test_load_json_file_returns_empty_dict_and_logs_on_invalid_json(self):
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False
        ) as temp_file:
            temp_file.write("{invalid json")
            bad_json_path = temp_file.name

        try:
            with patch.dict(
                os.environ, {"PLAINBOX_PROVIDER_DATA": ""}, clear=False
            ):
                with patch("general_utils.logging.warning") as mock_warning:
                    data = general_utils.load_json_file(
                        bad_json_path, enable_logger=True
                    )

            self.assertEqual(data, {})
            mock_warning.assert_called_once()
        finally:
            os.remove(bad_json_path)

    def test_load_json_file_returns_loaded_value_on_non_object_json(self):
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False
        ) as temp_file:
            temp_file.write('["not", "an", "object"]')
            non_object_json_path = temp_file.name

        try:
            with patch.dict(
                os.environ, {"PLAINBOX_PROVIDER_DATA": ""}, clear=False
            ):
                data = general_utils.load_json_file(non_object_json_path)

            self.assertEqual(data, ["not", "an", "object"])
        finally:
            os.remove(non_object_json_path)

    def test_load_json_file_returns_empty_dict_on_invalid_json(self):
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False
        ) as temp_file:
            temp_file.write("{invalid json")
            bad_json_path = temp_file.name

        try:
            with patch.dict(
                os.environ, {"PLAINBOX_PROVIDER_DATA": ""}, clear=False
            ):
                data = general_utils.load_json_file(bad_json_path)

            self.assertEqual(data, {})
        finally:
            os.remove(bad_json_path)

    def test_load_json_file_returns_empty_dict_when_missing_file(self):
        with patch.dict(
            os.environ, {"PLAINBOX_PROVIDER_DATA": ""}, clear=False
        ):
            data = general_utils.load_json_file("missing-file.json")

        self.assertEqual(data, {})

    def test_load_json_file_returns_empty_dict_for_empty_path(self):
        self.assertEqual(general_utils.load_json_file(""), {})

    @patch("general_utils.logging.warning")
    def test_load_json_file_logs_warning_when_relative_path_without_provider_data(
        self,
        mock_warning,
    ):
        with patch.dict(
            os.environ, {"PLAINBOX_PROVIDER_DATA": ""}, clear=False
        ):
            data = general_utils.load_json_file(
                "relative/config.json",
                enable_logger=True,
            )

        self.assertEqual(data, {})
        mock_warning.assert_called_once()


class TestFindFullPathOfBinary(unittest.TestCase):
    @patch("general_utils.Path.is_file", return_value=True)
    @patch("general_utils.Path.is_absolute", return_value=True)
    def test_find_full_path_of_binary_accepts_existing_absolute_path(
        self,
        _mock_is_absolute,
        _mock_is_file,
    ):
        command = "/usr/bin/fake-cmd"
        self.assertEqual(
            general_utils.find_full_path_of_binary(command),
            command,
        )

    @patch("general_utils.Path.stat")
    @patch("general_utils.Path.is_file")
    @patch("general_utils.Path.is_absolute", return_value=False)
    def test_find_full_path_of_binary_uses_priority_search_paths(
        self,
        _mock_is_absolute,
        mock_is_file,
        mock_stat,
    ):
        mock_is_file.side_effect = [False, False, False, False, True]
        mock_stat.return_value = type("Stat", (), {"st_mode": 0o755})()

        self.assertEqual(
            general_utils.find_full_path_of_binary("mycmd"),
            "/usr/local/bin/mycmd",
        )

    @patch("general_utils.Path.is_file", return_value=False)
    @patch("general_utils.Path.is_absolute", return_value=False)
    def test_find_full_path_of_binary_returns_empty_string_when_not_found(
        self,
        _mock_is_absolute,
        _mock_is_file,
    ):
        self.assertEqual(
            general_utils.find_full_path_of_binary("missing-cmd"),
            "",
        )


class TestBuildCustomizedCommand(unittest.TestCase):
    _FAKE_STAT = type("Stat", (), {"st_mode": 0o755})()

    @patch(
        "general_utils.Path.stat",
        return_value=type("Stat", (), {"st_mode": 0o755})(),
    )
    @patch("general_utils.Path.is_file", return_value=True)
    def test_build_customized_command_builds_expected_command(
        self, _mock_is_file, _mock_stat
    ):
        command = general_utils.build_customized_command(
            full_path_cmd="/usr/bin/foo",
            cmd_config={
                "LD_LIBRARY_PATH": ["/path/to/lib1", "/path/to/lib2"],
                "VAR1": "value1",
                "VAR2": "value2",
            },
        )

        self.assertEqual(
            command,
            'LD_LIBRARY_PATH="/path/to/lib1:/path/to/lib2:$LD_LIBRARY_PATH" '
            'VAR1="value1" VAR2="value2" /usr/bin/foo',
        )

    def test_build_customized_command_rejects_non_absolute_path(self):
        with self.assertRaisesRegex(TypeError, "absolute path"):
            general_utils.build_customized_command("foo", {})

    def test_build_customized_command_rejects_non_string_path(self):
        with self.assertRaisesRegex(TypeError, "string type"):
            general_utils.build_customized_command(None, {})

    @patch(
        "general_utils.Path.stat",
        return_value=type("Stat", (), {"st_mode": 0o755})(),
    )
    @patch("general_utils.Path.is_file", return_value=True)
    def test_build_customized_command_rejects_non_dict_config(
        self, _mock_is_file, _mock_stat
    ):
        with self.assertRaisesRegex(TypeError, "config must be a dictionary"):
            general_utils.build_customized_command("/usr/bin/foo", None)

    @patch(
        "general_utils.Path.stat",
        return_value=type("Stat", (), {"st_mode": 0o755})(),
    )
    @patch("general_utils.Path.is_file", return_value=True)
    def test_build_customized_command_rejects_invalid_ld_library_path(
        self, _mock_is_file, _mock_stat
    ):
        with self.assertRaisesRegex(ValueError, "LD_LIBRARY_PATH"):
            general_utils.build_customized_command(
                "/usr/bin/foo",
                {"LD_LIBRARY_PATH": "bad"},
            )

        with self.assertRaisesRegex(ValueError, "LD_LIBRARY_PATH"):
            general_utils.build_customized_command(
                "/usr/bin/foo",
                {"LD_LIBRARY_PATH": ["ok", 1]},
            )

    @patch(
        "general_utils.Path.stat",
        return_value=type("Stat", (), {"st_mode": 0o755})(),
    )
    @patch("general_utils.Path.is_file", return_value=True)
    def test_build_customized_command_rejects_non_string_env_values(
        self, _mock_is_file, _mock_stat
    ):
        with self.assertRaisesRegex(ValueError, "map env names"):
            general_utils.build_customized_command(
                "/usr/bin/foo",
                {"VAR": 1},
            )


class TestResolveExecutableCommands(unittest.TestCase):
    def _write_json(self, tmp_dir, filename, payload):
        file_path = os.path.join(tmp_dir, filename)
        with open(file_path, "w", encoding="utf-8") as file_obj:
            json.dump(payload, file_obj)
        return file_path

    @patch(
        "general_utils.find_full_path_of_binary",
        return_value="/usr/bin/clinfo",
    )
    def test_resolve_uses_default_command_when_no_json_path(self, _mock_find):
        result = general_utils.resolve_executable_commands(["clinfo"])

        self.assertEqual(result, {"clinfo": "/usr/bin/clinfo"})

    @patch(
        "general_utils.find_full_path_of_binary",
        return_value="/usr/bin/clinfo",
    )
    def test_resolve_falls_back_when_json_file_missing(self, _mock_find):
        with patch.dict(
            os.environ,
            {"EXECUTABLE_JSON_PATH": "/tmp/definitely-not-existing.json"},
            clear=False,
        ):
            result = general_utils.resolve_executable_commands(["clinfo"])

        self.assertEqual(result, {"clinfo": "/usr/bin/clinfo"})

    @patch(
        "general_utils.find_full_path_of_binary",
        return_value="/usr/bin/clinfo",
    )
    def test_resolve_falls_back_on_relative_path_without_provider_data(
        self,
        _mock_find,
    ):
        with patch.dict(
            os.environ,
            {"EXECUTABLE_JSON_PATH": "relative.json"},
            clear=True,
        ):
            result = general_utils.resolve_executable_commands(["clinfo"])

        self.assertEqual(result, {"clinfo": "/usr/bin/clinfo"})

    @patch(
        "general_utils.find_full_path_of_binary",
        return_value="/usr/bin/clinfo",
    )
    @patch(
        "general_utils.build_customized_command", return_value="custom-clinfo"
    )
    def test_resolve_uses_customized_config_when_json_exists(
        self,
        mock_build,
        _mock_find,
    ):
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = self._write_json(
                tmp_dir,
                "exec.json",
                {
                    "clinfo": {
                        "LD_LIBRARY_PATH": ["/custom/lib"],
                        "MY_ENV": "1",
                    }
                },
            )

            with patch.dict(
                os.environ,
                {"EXECUTABLE_JSON_PATH": json_path},
                clear=False,
            ):
                result = general_utils.resolve_executable_commands(["clinfo"])

        self.assertEqual(result, {"clinfo": "custom-clinfo"})
        mock_build.assert_called_once_with(
            full_path_cmd="/usr/bin/clinfo",
            cmd_config={
                "LD_LIBRARY_PATH": ["/custom/lib"],
                "MY_ENV": "1",
            },
            enable_logger=False,
        )

    @patch(
        "general_utils.find_full_path_of_binary",
        return_value="/usr/bin/clinfo",
    )
    @patch(
        "general_utils.build_customized_command",
        side_effect=TypeError("full_path_cmd must be a string type"),
    )
    def test_resolve_raises_when_customization_build_fails(
        self,
        _mock_build,
        _mock_find,
    ):
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = self._write_json(
                tmp_dir,
                "exec.json",
                {"clinfo": {}},
            )

            with patch.dict(
                os.environ,
                {"EXECUTABLE_JSON_PATH": json_path},
                clear=False,
            ):
                with self.assertRaisesRegex(TypeError, "full_path_cmd"):
                    general_utils.resolve_executable_commands(["clinfo"])

    @patch("general_utils.find_full_path_of_binary", return_value="")
    def test_resolve_raises_when_binary_resolution_fails_with_custom_json(
        self,
        _mock_find,
    ):
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = self._write_json(
                tmp_dir,
                "exec.json",
                {"clinfo": {}},
            )

            with patch.dict(
                os.environ,
                {"EXECUTABLE_JSON_PATH": json_path},
                clear=False,
            ):
                with self.assertRaisesRegex(TypeError, "absolute path"):
                    general_utils.resolve_executable_commands(["clinfo"])

    @patch(
        "general_utils.find_full_path_of_binary",
        side_effect=["/usr/bin/cmd-a", "/usr/bin/cmd-b"],
    )
    def test_resolve_multiple_commands_in_one_call(self, _mock_find):
        with patch.dict(
            os.environ,
            {"EXECUTABLE_JSON_PATH": ""},
            clear=False,
        ):
            result = general_utils.resolve_executable_commands(
                ["cmd-a", "cmd-b"]
            )

        self.assertEqual(
            result,
            {"cmd-a": "/usr/bin/cmd-a", "cmd-b": "/usr/bin/cmd-b"},
        )

    @patch(
        "general_utils.find_full_path_of_binary",
        return_value="/usr/bin/clinfo",
    )
    def test_resolve_deduplicates_input_commands(self, _mock_find):
        with patch.dict(
            os.environ,
            {"EXECUTABLE_JSON_PATH": ""},
            clear=False,
        ):
            result = general_utils.resolve_executable_commands(
                ["clinfo", "clinfo"]
            )

        self.assertEqual(result, {"clinfo": "/usr/bin/clinfo"})


class TestResolveDefaultCommands(unittest.TestCase):
    @patch(
        "general_utils.find_full_path_of_binary",
        side_effect=["/usr/bin/a", ""],
    )
    def test_resolve_default_commands_maps_each_command(self, _mock_find):
        result = general_utils.resolve_default_commands(["a", "b"])
        self.assertEqual(result, {"a": "/usr/bin/a", "b": ""})


class TestWithResolvedCommands(unittest.TestCase):
    def test_rejects_empty_default_commands(self):
        with self.assertRaisesRegex(ValueError, "default_commands"):
            general_utils.with_resolved_commands([])

    def test_rejects_empty_inject_param(self):
        with self.assertRaisesRegex(ValueError, "inject_param"):
            general_utils.with_resolved_commands(["clinfo"], inject_param="")

    @patch(
        "general_utils.resolve_executable_commands",
        return_value={"clinfo": "custom-clinfo"},
    )
    def test_injects_resolved_commands_mapping(self, mock_resolve):
        @general_utils.with_resolved_commands(["clinfo"])
        def _func(**kwargs):
            return kwargs["resolved_commands"]

        result = _func()

        self.assertEqual(result, {"clinfo": "custom-clinfo"})
        mock_resolve.assert_called_once_with(
            default_commands=["clinfo"],
            enable_logger=False,
        )

    @patch(
        "general_utils.resolve_executable_commands",
        return_value={"clinfo": "custom-clinfo"},
    )
    def test_uses_custom_inject_param(self, _mock_resolve):
        @general_utils.with_resolved_commands(
            ["clinfo"],
            inject_param="commands",
        )
        def _func(**kwargs):
            return kwargs["commands"]

        self.assertEqual(_func(), {"clinfo": "custom-clinfo"})

    @patch(
        "general_utils.resolve_executable_commands",
        return_value={"clinfo": "custom-clinfo"},
    )
    def test_overrides_existing_injected_kwarg(self, _mock_resolve):
        @general_utils.with_resolved_commands(["clinfo"])
        def _func(**kwargs):
            return kwargs["resolved_commands"]

        self.assertEqual(
            _func(resolved_commands={"clinfo": "manual"}),
            {"clinfo": "custom-clinfo"},
        )

    @patch(
        "general_utils.resolve_executable_commands",
        return_value={"clinfo": "custom-clinfo"},
    )
    def test_forwards_args_and_kwargs(self, _mock_resolve):
        @general_utils.with_resolved_commands(["clinfo"])
        def _func(prefix, *, suffix="", resolved_commands=None):
            self.assertEqual(
                resolved_commands,
                {"clinfo": "custom-clinfo"},
            )
            return prefix + suffix

        self.assertEqual(_func("a", suffix="b"), "ab")

    @patch(
        "general_utils.resolve_executable_commands",
        return_value={"a": "/usr/bin/a"},
    )
    def test_deduplicates_default_commands_for_resolver(self, mock_resolve):
        @general_utils.with_resolved_commands(["a", "a"])
        def _func(**kwargs):
            return kwargs["resolved_commands"]

        _func()

        mock_resolve.assert_called_once_with(
            default_commands=["a"],
            enable_logger=False,
        )

    @patch(
        "general_utils.resolve_executable_commands",
        return_value={"clinfo": ""},
    )
    def test_raises_when_unresolved_in_strict_mode(self, _mock_resolve):
        @general_utils.with_resolved_commands(["clinfo"], strict=True)
        def _func(**_kwargs):
            return None

        with self.assertRaisesRegex(ValueError, "Failed to resolve"):
            _func()

    @patch(
        "general_utils.resolve_executable_commands",
        return_value={"clinfo": ""},
    )
    def test_allows_unresolved_in_non_strict_mode(self, _mock_resolve):
        @general_utils.with_resolved_commands(["clinfo"], strict=False)
        def _func(**kwargs):
            return kwargs["resolved_commands"]

        self.assertEqual(_func(), {"clinfo": ""})

    @patch(
        "general_utils.resolve_executable_commands",
        return_value={"clinfo": "custom-clinfo"},
    )
    def test_passes_enable_logger_to_resolver(self, mock_resolve):
        @general_utils.with_resolved_commands(["clinfo"], enable_logger=True)
        def _func(**kwargs):
            return kwargs["resolved_commands"]

        _func()

        mock_resolve.assert_called_once_with(
            default_commands=["clinfo"],
            enable_logger=True,
        )


if __name__ == "__main__":
    unittest.main()
