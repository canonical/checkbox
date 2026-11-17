import unittest
from unittest.mock import patch, MagicMock
import urwid
from checkbox_ng.urwid_ui import (
    CategoryBrowser,
    ManifestBrowser,
    ReRunBrowser,
    TestPlanBrowser,
)


class TestCategoryBrowser(unittest.TestCase):
    def setUp(self):
        tests = [
            {
                "id": "namespace::job",
                "partial_id": "job",
                "name": "Job summary",
                "category_id": "category",
                "category_name": "Category",
            }
        ]
        browser = CategoryBrowser("Test", tests)
        category_node = browser.listbox.body.root_node.get_child_node(
            "category"
        )
        self.category = category_node.get_widget()
        self.job = category_node.get_child_node("namespace::job").get_widget()

    def test_toggle_job_selection(self):
        self.job.keypress((80,), " ")

        self.assertFalse(self.job.flagged)
        columns = self.job._w.base_widget
        self.assertIs(columns.contents[0][0], self.job.unselected)

    def test_expand_category(self):
        self.category.keypress((80,), "enter")

        self.assertTrue(self.category.expanded)
        columns = self.category._w.base_widget
        self.assertIs(columns.contents[2][0], self.category.expanded_icon)

    @patch("checkbox_ng.urwid_ui.show_job_ids", False)
    def test_show_job_ids(self):
        self.job.keypress((80,), "i")

        padding = self.job._w.base_widget.contents[-1][0]
        self.assertEqual(padding.original_widget.text, "job")


class TestReRunBrowser(unittest.TestCase):
    def test_starts_deselected(self):
        tests = [
            {
                "id": "namespace::job",
                "partial_id": "job",
                "name": "Job summary",
                "category_name": "Category",
                "outcome": "fail",
            }
        ]
        browser = ReRunBrowser("Test", tests, [])
        category_node = browser.root_node.get_child_node(
            "fail"
        ).get_child_node("Category")
        job = category_node.get_child_node("namespace::job").get_widget()

        self.assertFalse(job.flagged)
        columns = job._w.base_widget
        self.assertIs(columns.contents[0][0], job.unselected)


class TestTestPlanBrowser(unittest.TestCase):
    def setUp(self):
        test_plans = [
            {"id": "namespace::first", "name": "Alpha plan"},
            {"id": "namespace::second", "name": "Beta plan"},
        ]
        self.browser = TestPlanBrowser("Test", test_plans, None)
        self.browser.loop = MagicMock(widget=self.browser.frame)

    def test_start_filtering(self):
        self.browser.unhandled_input("f")

        self.assertTrue(self.browser.filtering)
        self.assertEqual(self.browser.frame.focus_position, "footer")

    def test_apply_filter(self):
        self.browser.unhandled_input("f")
        self.browser.filter_footer.base_widget.set_edit_text("alpha")
        self.browser.unhandled_input("enter")

        self.assertFalse(self.browser.filtering)
        self.assertEqual(self.browser.frame.focus_position, "body")
        tp_ids = [b.tp_id for b in self.browser.radio_button_group]
        self.assertEqual(tp_ids, ["namespace::first"])
        self.assertEqual(len(self.browser.button_pile.contents), 1)


class TestManifestBrowser(unittest.TestCase):

    @patch("checkbox_ng.urwid_ui.urwid.MainLoop")
    def test_handle_focused_question_input_empty_pile(self, mock_mainloop):
        browser = ManifestBrowser("Test", {})
        # No items in the pile ⟶ nothing happens
        browser.handle_focused_question_input("Any key")

    @patch("checkbox_ng.urwid_ui.urwid.MainLoop")
    def test_handle_focused_question_input(self, mock_mainloop):

        cases = [
            # (question type, key pressed, expected input sequence sent to UI loop)
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

        # Trying to submit without having answered all questions should
        # not raise (close the ManifestBrowser and continue the test run)
        browser.handle_submit_key()

    def test_handle_submit_key_all_answered(self):
        browser = ManifestBrowser("Test", {})
        q1 = MagicMock()
        q1.value = 1
        q2 = MagicMock()
        q2.value = 42
        browser._question_store = [q1, q2]

        # Submitting after all answers were given closes the ManifesBrowser
        with self.assertRaises(urwid.ExitMainLoop):
            browser.handle_submit_key()

    def test_has_visible_manifests_with_visible_manifests(self):
        manifest_repr = {
            "section1": [
                {"id": "visible1", "hidden": False},
                {"id": "hidden1", "hidden": True},
            ],
            "section2": [
                {"id": "visible2", "hidden": False},
            ],
        }

        self.assertTrue(ManifestBrowser.has_visible_manifests(manifest_repr))

    def test_has_visible_manifests_no_visible_manifests(self):
        manifest_repr = {
            "section1": [
                {"id": "hidden1", "hidden": True},
                {"id": "hidden2", "hidden": True},
            ],
            "section2": [
                {"id": "hidden3", "hidden": True},
            ],
        }

        self.assertFalse(ManifestBrowser.has_visible_manifests(manifest_repr))

    def test_has_visible_manifests_missing_hidden_field(self):
        manifest_repr = {
            "section1": [
                {
                    "id": "default_visible",
                    "value": "test",
                },  # No 'hidden' field ⟶ hidden==False
                {"id": "hidden1", "hidden": True},
            ]
        }

        self.assertTrue(ManifestBrowser.has_visible_manifests(manifest_repr))

    def test_has_visible_manifests_empty_manifest(self):
        self.assertFalse(ManifestBrowser.has_visible_manifests({}))

    def test_get_flattened_values(self):
        manifest_repr = {
            "section1": [
                {"id": "visible1", "value": "visible_1", "hidden": False},
                {"id": "hidden1", "value": "hidden_1", "hidden": True},
            ],
            "section2": [
                {"id": "visible2", "value": "visible_2", "hidden": False},
                {"id": "hidden2", "value": "hidden_2", "hidden": True},
            ],
        }

        result = ManifestBrowser.get_flattened_values(manifest_repr)

        expected = {
            "visible1": "visible_1",
            "hidden1": "hidden_1",
            "visible2": "visible_2",
            "hidden2": "hidden_2",
        }
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
