from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

import executable_resource


class TestIterIfAccessible(TestCase):

    @patch("executable_resource.Path.iterdir")
    def test_iterdir_success(self, iterdir_mock):
        iterdir_mock.return_value = iter(
            [Path("/usr/bin/ls"), Path("/usr/bin/cat")]
        )
        result = list(executable_resource.iter_if_accessible(Path("/usr/bin")))
        self.assertEqual(result, [Path("/usr/bin/ls"), Path("/usr/bin/cat")])

    @patch("executable_resource.Path.iterdir")
    def test_iterdir_oserror_while_consuming(self, iterdir_mock):
        class FailingIterator:
            def __iter__(self):
                return self

            def __next__(self):
                raise OSError("Permission denied")

        iterdir_mock.return_value = FailingIterator()
        result = list(
            executable_resource.iter_if_accessible(Path("/no/access"))
        )
        self.assertEqual(result, [])

    @patch("executable_resource.Path.iterdir")
    def test_iterdir_oserror(self, iterdir_mock):
        iterdir_mock.side_effect = OSError("Permission denied")
        result = list(
            executable_resource.iter_if_accessible(Path("/no/access"))
        )
        self.assertEqual(result, [])


class TestExecutableResource(TestCase):

    @patch("executable_resource.Path.is_file", return_value=True)
    @patch("executable_resource.print")
    @patch("executable_resource.iter_if_accessible")
    @patch("executable_resource.os.access")
    @patch("executable_resource.os.get_exec_path")
    def test_main(
        self,
        get_exec_path_mock,
        access_mock,
        iter_mock,
        print_mock,
        is_file_mock,
    ):
        text = ""

        def store(*args, **kwargs):
            nonlocal text
            text += " ".join(args) + "\n"

        print_mock.side_effect = store

        get_exec_path_mock.return_value = ["/usr/bin", "/usr/local/bin"]

        def iter_side_effect(path):
            resolved = str(path)
            if "local" in resolved:
                return iter([path / "cat", path / "ls"])
            return iter([path / "custom_tool", path / "not_exec"])

        iter_mock.side_effect = iter_side_effect

        def access_side_effect(path, mode):
            return "not_exec" not in str(path)

        access_mock.side_effect = access_side_effect

        executable_resource.main()

        lines = text.strip().splitlines()
        self.assertNotIn("name: not_exec", lines)
        self.assertIn("name: cat", lines)
        self.assertIn("name: custom_tool", lines)
        self.assertIn("name: ls", lines)

    @patch("executable_resource.Path.exists", return_value=False)
    @patch("executable_resource.print")
    @patch("executable_resource.iter_if_accessible")
    @patch("executable_resource.os.get_exec_path")
    def test_main_skips_nonexistent_paths(
        self,
        get_exec_path_mock,
        iter_mock,
        print_mock,
        exists_mock,
    ):
        get_exec_path_mock.return_value = ["/does/not/exist"]

        executable_resource.main()

        iter_mock.assert_not_called()
        print_mock.assert_not_called()
