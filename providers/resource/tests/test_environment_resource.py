import unittest
from textwrap import dedent
from unittest import TestCase
from unittest.mock import MagicMock, patch

import environment_resource


class TestEnvironmentResource(TestCase):

    @patch("environment_resource.print")
    @patch("os.environ")
    def test_main(self, environ_mock, print_mock):
        text = ""

        def store(*args, **kwargs):
            nonlocal text
            text += " ".join(args) + "\n"

        print_mock.side_effect = store
        environ = {
            "SOME": "1",
            "OTHER": dedent("""
            multiline environment
            variable
            """).strip(),
            # non-regression, this was a bug in the old resource
            "LAST": "bug:somevalue",
        }
        environ_mock.items = environ.items

        environment_resource.main()

        self.assertIn("SOME: 1", text.strip())
        self.assertIn("LAST: bug:somevalue", text.strip())
        # newlines shouldn't break the resource
        self.assertEqual(len(text.splitlines()), len(environ))
