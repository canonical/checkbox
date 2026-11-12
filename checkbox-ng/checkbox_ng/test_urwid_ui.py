import unittest
from unittest.mock import patch, MagicMock
import urwid
from checkbox_ng import urwid_ui
from checkbox_ng.urwid_ui import ManifestBrowser


class TestCategoryBrowser(unittest.TestCase):
    def setUp(self):
        patcher = patch.multiple(
            urwid_ui,
            _widget_cache={},
            test_info_list=(),
            show_job_ids=False,
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        self.tests = [
            {
                "id": "namespace::job",
                "partial_id": "job",
                "name": "Job summary",
                "category_id": "category",
                "category_name": "Category",
                "outcome": "fail",
            }
        ]
        self.browser = urwid_ui.CategoryBrowser("Select jobs", self.tests)
        self.root = self.browser.listbox.body.root_node
        self.category = self.root.get_child_node("category").get_widget()
        self.job = (
            self.category.get_node()
            .get_child_node("namespace::job")
            .get_widget()
        )

    def test_toggle_selection_preserves_layout(self):
        columns = self.job._w.base_widget
        options = [options for widget, options in columns.contents]
        self.assertEqual(options[0], columns.options("given", 3))

        for selected in (False, True):
            with self.subTest(selected=selected):
                self.job.keypress((80,), " ")

                self.assertEqual(self.job.flagged, selected)
                self.assertEqual(self.category.flagged, selected)
                self.assertEqual(self.root.get_widget().flagged, selected)
                self.assertIs(
                    columns.contents[0][0],
                    self.job.selected if selected else self.job.unselected,
                )
                self.assertEqual(
                    [options for widget, options in columns.contents], options
                )

    def test_expand_collapse_preserves_layout(self):
        columns = self.category._w.base_widget
        options = [options for widget, options in columns.contents]
        self.assertEqual(options[2], columns.options("given", 1))

        for expanded in (True, False):
            with self.subTest(expanded=expanded):
                self.category.keypress((80,), "enter")

                self.assertEqual(self.category.expanded, expanded)
                self.assertIs(
                    columns.contents[2][0],
                    (
                        self.category.expanded_icon
                        if expanded
                        else self.category.unexpanded_icon
                    ),
                )
                self.assertEqual(
                    [options for widget, options in columns.contents], options
                )
                self.browser.view.render((80, 24), focus=True)

    def test_toggle_job_ids_preserves_layout(self):
        columns = self.job._w.base_widget
        options = columns.contents[-1][1]

        for key, text in (("i", "job"), ("I", "Job summary")):
            with self.subTest(key=key):
                self.job.keypress((80,), key)

                padding, new_options = columns.contents[-1]
                self.assertEqual(padding.original_widget.get_text()[0], text)
                self.assertEqual(padding.left, self.job.get_indent_cols())
                self.assertEqual(new_options, options)

    def test_rerun_browser_starts_deselected(self):
        browser = urwid_ui.ReRunBrowser("Rerun jobs", self.tests, [])
        root = browser.root_node.get_widget()

        self.assertFalse(root.flagged)
        self.assertFalse(urwid_ui._widget_cache["namespace::job"].flagged)
        browser.view.render((80, 24), focus=True)


class TestTestPlanBrowser(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(
            urwid.Frame, "_command_map", urwid.Frame._command_map.copy()
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        self.test_plans = [
            {"id": "namespace::first", "name": "Alpha plan"},
            {"id": "namespace::second", "name": "Beta plan"},
        ]
        self.browser = urwid_ui.TestPlanBrowser(
            "Select test plan",
            self.test_plans,
            selection="namespace::second",
        )
        self.browser.loop = MagicMock(widget=self.browser.frame)

    def test_cancel_filter_restores_focus_and_selection(self):
        for key in ("/", "s", "f"):
            with self.subTest(key=key):
                self.browser.unhandled_input(key)

                self.assertTrue(self.browser.filtering)
                self.assertEqual(self.browser.frame.focus_position, "footer")
                self.assertIs(
                    self.browser.frame.footer, self.browser.filter_footer
                )
                self.browser.frame.render((80, 24), focus=True)

                self.browser.unhandled_input("esc")

                self.assertFalse(self.browser.filtering)
                self.assertEqual(self.browser.frame.focus_position, "body")
                self.assertIs(
                    self.browser.frame.footer, self.browser.default_footer
                )
                self.assertTrue(self.browser.radio_button_group[1].state)

    def test_filter_by_name_id_and_clear(self):
        cases = [
            ("ALPHA", ["namespace::first"]),
            ("SECOND", ["namespace::second"]),
            ("", ["namespace::first", "namespace::second"]),
        ]
        pile = self.browser.button_pile
        for query, expected_ids in cases:
            with self.subTest(query=query):
                self.browser.unhandled_input("/")
                self.browser.filter_footer.base_widget.edit_text = query
                self.browser.unhandled_input("enter")

                self.assertIs(self.browser.button_pile, pile)
                self.assertEqual(
                    [
                        button.tp_id
                        for button in self.browser.radio_button_group
                    ],
                    expected_ids,
                )
                self.assertEqual(
                    [
                        widget.base_widget.tp_id
                        for widget, options in pile.contents
                    ],
                    expected_ids,
                )
                self.assertTrue(
                    all(
                        options == pile.options()
                        for _, options in pile.contents
                    )
                )
                self.assertFalse(self.browser.filtering)
                self.assertEqual(self.browser.frame.focus_position, "body")
                if "namespace::second" in expected_ids:
                    self.assertTrue(self.browser.radio_button_group[-1].state)
                self.browser.frame.render((80, 24), focus=True)


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
