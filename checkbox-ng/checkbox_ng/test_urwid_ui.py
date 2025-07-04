import unittest
from unittest.mock import patch, MagicMock
import urwid
from checkbox_ng.urwid_ui import ManifestBrowser


class ManifestBrowserTest(unittest.TestCase):

    @patch("checkbox_ng.urwid_ui.urwid.MainLoop")
    def test_handle_focused_question_input_empty_pile(self, mock_mainloop):
        browser = ManifestBrowser("Test", {})
        # No items in the pile ⟶ nothing happens
        browser.handle_focused_question_input("Any key")

    @patch("checkbox_ng.urwid_ui.urwid.MainLoop")
    def test_handle_focused_question_input(self, mock_mainloop):
        cases = [
            ("bool", "y", ["left", " ", "down"]),
            ("bool", "n", ["right", " ", "down"]),
            ("natural", "enter", ["down"]),
        ]

        for value_type, key, expected_calls in cases:
            with self.subTest(key=key):
                browser = ManifestBrowser("Test", {})
                browser._pile = MagicMock()
                bool_question = MagicMock()
                bool_question._value_type = value_type
                browser._pile.focus = bool_question
                browser.loop = MagicMock()
                browser.handle_focused_question_input(key)
                browser.loop.process_input.assert_called_with(expected_calls)

    def test_handle_submit_key_not_all_answered(self):
        browser = ManifestBrowser("Test", {})
        q1 = MagicMock()
        q1.value = None  # Unanswered question
        q2 = MagicMock()
        q2.value = 42
        browser._question_store = [q1, q2]

        # Should not raise
        browser.handle_submit_key()

    def test_handle_submit_key_all_answered(self):
        browser = ManifestBrowser("Test", {})
        q1 = MagicMock()
        q1.value = 1
        q2 = MagicMock()
        q2.value = 42
        browser._question_store = [q1, q2]

        with self.assertRaises(urwid.ExitMainLoop):
            browser.handle_submit_key()


if __name__ == "__main__":
    unittest.main()
