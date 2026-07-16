"""Unit tests for gen_launcher data layer."""

import importlib
import importlib.util
import sys
import tempfile
import textwrap
import types
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).parent / "gen_launcher.py"


def _load_module():
    sys.path.insert(0, str(_SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("gen_launcher", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    # urwid may not be available in test environment; stub it out
    urwid_stub = types.ModuleType("urwid")

    class _WidgetWrap:
        def __init__(self, widget=None):
            self._w = widget

    class _Widget:
        def __init__(self):
            pass

        def _invalidate(self):
            pass

    class _Columns:
        """Minimal stand-in for urwid.Columns' focus-switching behaviour,
        just enough for _SwitchColumns (module-level subclass) to import
        and for its keypress-diffing logic to be exercised in tests."""

        def __init__(self, widget_list, dividechars=0, **kwargs):
            self.contents = list(widget_list)
            self.focus_position = 0

        def keypress(self, size, key):
            if key == "right" and self.focus_position < len(self.contents) - 1:
                self.focus_position += 1
                return None
            if key == "left" and self.focus_position > 0:
                self.focus_position -= 1
                return None
            return key

    urwid_stub.WidgetWrap = _WidgetWrap  # minimal stub for import
    urwid_stub.Columns = _Columns
    urwid_stub.Widget = _Widget
    sys.modules.setdefault("urwid", urwid_stub)
    sys.modules["gen_launcher"] = mod
    spec.loader.exec_module(mod)
    return mod


gl = _load_module()

# ── urwid stubs needed by ItemRow ────────────────────────────────
_urwid_stub = sys.modules["urwid"]


class _FakeEdit:
    def __init__(self, caption="", edit_text=""):
        self._text = edit_text

    @property
    def edit_text(self):
        return self._text

    def get_edit_text(self):
        return self._text

    def set_edit_text(self, t):
        self._text = t

    def set_edit_pos(self, pos):
        pass

    def get_text(self):
        return self._text, []

    def rows(self, size, focus=False):
        return 1

    def keypress(self, size, key):
        return key

    def render(self, size, focus=False):
        return None


class _FakeText:
    def __init__(self, *args, **kwargs):
        pass

    def rows(self, size, focus=False):
        return 1


class _FakeAttrMap:
    def __init__(self, *args, **kwargs):
        pass

    def rows(self, size, focus=False):
        return 1

    def keypress(self, size, key):
        return key


_urwid_stub.Edit = _FakeEdit
_urwid_stub.Text = _FakeText
_urwid_stub.AttrMap = _FakeAttrMap


class TestCollectItems(unittest.TestCase):
    def _cache(self):
        return {
            "manifest_entries": {
                "has_gpio": {
                    "full_id": "ns::has_gpio",
                    "name": "GPIO",
                    "prompt": "Has GPIO?",
                    "value_type": "bool",
                }
            },
            "test_plans": {},
            "jobs": {
                "ns::j1": {
                    "id": "ns::j1",
                    "summary": "J1",
                    "description": "",
                    "environ": ["MY_VAR"],
                    "manifest": ["has_gpio"],
                    "command": "",
                    "provider": "ns",
                    "unit_type": "job",
                },
            },
        }

    def test_manifest_item_created(self):
        items = gl.collect_items("ns::p", {"ns::j1"}, self._cache())
        manifest = [i for i in items if i.kind == "manifest"]
        self.assertEqual(len(manifest), 1)
        self.assertEqual(manifest[0].key, "ns::has_gpio")
        self.assertEqual(manifest[0].name, "GPIO")
        self.assertEqual(manifest[0].value_type, "bool")

    def test_environ_item_created(self):
        items = gl.collect_items("ns::p", {"ns::j1"}, self._cache())
        environ = [i for i in items if i.kind == "environ"]
        self.assertEqual(len(environ), 1)
        self.assertEqual(environ[0].key, "MY_VAR")

    def test_manifest_before_environ(self):
        items = gl.collect_items("ns::p", {"ns::j1"}, self._cache())
        kinds = [i.kind for i in items]
        self.assertLess(kinds.index("manifest"), kinds.index("environ"))

    def test_hidden_manifest_key_excluded_even_if_job_requires_it(self):
        """A job may reference a hidden manifest key (bare id starting
        with '_') via `requires:` even though no `manifest entry` unit
        defines it (since it was filtered out of manifest_entries by
        build_cache). collect_items must still exclude it."""
        cache = self._cache()
        cache["jobs"]["ns::j2"] = {
            "id": "ns::j2",
            "summary": "J2",
            "description": "",
            "environ": [],
            "manifest": ["_hidden_flag"],
            "command": "",
            "provider": "ns",
            "unit_type": "job",
        }
        items = gl.collect_items("ns::p", {"ns::j1", "ns::j2"}, cache)
        manifest_keys = [i.bare_key for i in items if i.kind == "manifest"]
        self.assertNotIn("_hidden_flag", manifest_keys)


class TestWriteLauncher(unittest.TestCase):
    def _items(self):
        return [
            gl.Item(
                kind="manifest",
                key="ns::has_gpio",
                bare_key="has_gpio",
                value="True",
                value_type="bool",
            ),
            gl.Item(
                kind="environ",
                key="MYVAR",
                bare_key="MYVAR",
                value="hello",
            ),
        ]

    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ce-oem-test"
            gl.write_launcher("ns::ce-oem-test", self._items(), out)
            self.assertTrue(out.exists())

    def test_shebang_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ce-oem-test"
            gl.write_launcher("ns::ce-oem-test", self._items(), out)
            lines = out.read_text().splitlines()
            self.assertEqual(lines[0], "#!/usr/bin/env checkbox-cli-wrapper")

    def test_sections_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ce-oem-test"
            gl.write_launcher("ns::ce-oem-test", self._items(), out)
            text = out.read_text()
            for section in (
                "[launcher]",
                "[test plan]",
                "[ui]",
                "[manifest]",
                "[environment]",
            ):
                self.assertIn(section, text)

    def test_plan_unit_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ce-oem-test"
            gl.write_launcher("ns::ce-oem-test", self._items(), out)
            self.assertIn("unit = ns::ce-oem-test", out.read_text())

    def test_manifest_value_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ce-oem-test"
            gl.write_launcher("ns::ce-oem-test", self._items(), out)
            self.assertIn("ns::has_gpio = True", out.read_text())

    def test_empty_manifest_written_as_false(self):
        items = [
            gl.Item(
                kind="manifest",
                key="ns::has_gpio",
                bare_key="has_gpio",
                value="",
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ce-oem-test"
            gl.write_launcher("ns::ce-oem-test", items, out)
            self.assertIn("ns::has_gpio = false\n", out.read_text())

    def test_no_manifest_section_when_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ce-oem-test"
            gl.write_launcher("ns::ce-oem-test", [], out)
            self.assertNotIn("[manifest]", out.read_text())


class TestParseExistingLauncher(unittest.TestCase):
    _SAMPLE = textwrap.dedent("""\
        #!/usr/bin/env checkbox-cli-wrapper
        [launcher]
        app_id = com.canonical.contrib:checkbox

        [manifest]
        com.canonical.contrib::has_gpio = True
        com.canonical.certification::has_edac_module = false

        [environment]
        RS485_CONFIG = /dev/ttyS0
        OTG =
    """)

    def test_parses_manifest_values(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".launcher", delete=False
        ) as f:
            f.write(self._SAMPLE)
            p = Path(f.name)
        try:
            d = gl.parse_existing_launcher(p)
            self.assertEqual(d["com.canonical.contrib::has_gpio"], "True")
            self.assertEqual(
                d["com.canonical.certification::has_edac_module"], "false"
            )
        finally:
            p.unlink(missing_ok=True)

    def test_parses_environment_values(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".launcher", delete=False
        ) as f:
            f.write(self._SAMPLE)
            p = Path(f.name)
        try:
            d = gl.parse_existing_launcher(p)
            self.assertEqual(d["RS485_CONFIG"], "/dev/ttyS0")
            self.assertEqual(d["OTG"], "")
        finally:
            p.unlink(missing_ok=True)

    def test_missing_file_returns_empty(self):
        d = gl.parse_existing_launcher(Path("/nonexistent/launcher"))
        self.assertEqual(d, {})

    def test_ignores_other_sections(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".launcher", delete=False
        ) as f:
            f.write(self._SAMPLE)
            p = Path(f.name)
        try:
            d = gl.parse_existing_launcher(p)
            self.assertNotIn("app_id", d)
        finally:
            p.unlink(missing_ok=True)


class TestApplyLauncherDefaults(unittest.TestCase):
    def _items(self):
        return [
            gl.Item(
                kind="manifest",
                key="ns::has_gpio",
                bare_key="has_gpio",
                value="",
            ),
            gl.Item(
                kind="environ",
                key="RS485_CONFIG",
                bare_key="RS485_CONFIG",
                value="",
            ),
        ]

    def test_applies_full_key_match(self):
        items = self._items()
        gl.apply_launcher_defaults(items, {"ns::has_gpio": "True"})
        self.assertEqual(items[0].value, "True")

    def test_applies_bare_key_match(self):
        items = self._items()
        gl.apply_launcher_defaults(items, {"has_gpio": "True"})
        self.assertEqual(items[0].value, "True")

    def test_applies_environ_match(self):
        items = self._items()
        gl.apply_launcher_defaults(items, {"RS485_CONFIG": "/dev/ttyS0"})
        self.assertEqual(items[1].value, "/dev/ttyS0")

    def test_unmatched_key_leaves_value_unchanged(self):
        items = self._items()
        gl.apply_launcher_defaults(items, {"other::key": "x"})
        self.assertEqual(items[0].value, "")

    def test_empty_defaults_is_noop(self):
        items = self._items()
        gl.apply_launcher_defaults(items, {})
        self.assertEqual(items[0].value, "")


class TestItemRowEditMode(unittest.TestCase):
    def _make_item(self, value="original"):
        return gl.Item(
            kind="manifest",
            key="ns::has_gpio",
            bare_key="has_gpio",
            value=value,
        )

    def test_e_activates_edit_mode(self):
        item = self._make_item()
        row = gl.ItemRow(item)
        self.assertFalse(row._editing)
        row.keypress((40,), "e")
        self.assertTrue(row._editing)

    def test_enter_commits_edit(self):
        item = self._make_item("original")
        row = gl.ItemRow(item)
        row.keypress((40,), "e")
        row._edit.set_edit_text("new value")
        row.keypress((40,), "enter")
        self.assertFalse(row._editing)
        self.assertEqual(item.value, "new value")

    def test_esc_cancels_edit(self):
        item = self._make_item("original")
        row = gl.ItemRow(item)
        row.keypress((40,), "e")
        row._edit.set_edit_text("discarded")
        row.keypress((40,), "esc")
        self.assertFalse(row._editing)
        self.assertEqual(item.value, "original")


class TestDescForItem(unittest.TestCase):
    """_desc_for_item() surfaces related jobs' _purpose for environ items."""

    def _desc(self, item):
        # The method only reads *item*, so it can be called unbound.
        return gl.LauncherEditorScreen._desc_for_item(None, item)

    def test_manifest_shows_name_and_prompt(self):
        item = gl.Item(
            kind="manifest",
            key="ns::has_gpio",
            bare_key="has_gpio",
            name="GPIO",
            prompt="Does this board have GPIO?",
        )
        desc = self._desc(item)
        self.assertIn("Name   : GPIO", desc)
        self.assertIn("Prompt : Does this board have GPIO?", desc)

    def test_environ_includes_related_job_purposes(self):
        item = gl.Item(
            kind="environ",
            key="GADGET_INTERFACE_FILE",
            bare_key="GADGET_INTERFACE_FILE",
            related_jobs=[
                {
                    "id": "com.canonical.certification::gadget/check",
                    "summary": "Check gadget",
                    "description": "Check if gadget interface is defined",
                    "purpose": "Check if gadget interface is defined",
                }
            ],
        )
        desc = self._desc(item)
        self.assertIn("- com.canonical.certification::gadget/check", desc)
        self.assertIn(
            "Purpose    : Check if gadget interface is defined", desc
        )
        # Job count is already shown in the right-top pane header, so it
        # shouldn't be repeated in the bottom description pane.
        self.assertNotIn("used by", desc)

    def test_environ_shows_both_purpose_and_description(self):
        """Real jobs like gadget/check-snap-interface-conf define both a
        short `_purpose` and a longer, different `_description`; the
        environ pane should show both, not let one shadow the other."""
        item = gl.Item(
            kind="environ",
            key="GADGET_INTERFACE_FILE",
            bare_key="GADGET_INTERFACE_FILE",
            related_jobs=[
                {
                    "id": "ns::gadget-job",
                    "summary": "",
                    "description": "Usage: create a JSON file with...",
                    "purpose": "Check if gadget interface file is defined",
                }
            ],
        )
        desc = self._desc(item)
        self.assertIn(
            "Purpose    : Check if gadget interface file is defined", desc
        )
        self.assertIn("Description: Usage: create a JSON file with...", desc)

    def test_environ_omits_description_line_when_identical_to_purpose(self):
        item = gl.Item(
            kind="environ",
            key="VAR",
            bare_key="VAR",
            related_jobs=[
                {
                    "id": "ns::a",
                    "summary": "",
                    "description": "Same text",
                    "purpose": "Same text",
                }
            ],
        )
        desc = self._desc(item)
        self.assertEqual(desc.count("Same text"), 1)
        self.assertNotIn("Description:", desc)

    def test_environ_falls_back_to_description_without_purpose(self):
        item = gl.Item(
            kind="environ",
            key="VAR",
            bare_key="VAR",
            related_jobs=[
                {"id": "ns::a", "summary": "", "description": "Fallback desc"}
            ],
        )
        desc = self._desc(item)
        self.assertIn("Description: Fallback desc", desc)
        self.assertNotIn("Purpose", desc)

    def test_environ_multiple_jobs_shows_hint_instead_of_details(self):
        """When more than one job uses a var, don't guess which job's
        purpose/description applies — point the user at the right-top
        pane to pick a specific job instead."""
        item = gl.Item(
            kind="environ",
            key="VAR",
            bare_key="VAR",
            related_jobs=[
                {"id": "ns::a", "summary": "", "purpose": "Purpose A"},
                {"id": "ns::b", "summary": "", "purpose": "Purpose B"},
            ],
        )
        desc = self._desc(item)
        self.assertIn("right pane", desc)
        self.assertNotIn("Purpose A", desc)
        self.assertNotIn("Purpose B", desc)

    def test_environ_no_related_jobs(self):
        item = gl.Item(
            kind="environ", key="VAR", bare_key="VAR", related_jobs=[]
        )
        desc = self._desc(item)
        self.assertEqual(desc, "(no related jobs found)")

    def test_environ_without_descriptions_has_no_purpose_section(self):
        item = gl.Item(
            kind="environ",
            key="VAR",
            bare_key="VAR",
            related_jobs=[{"id": "ns::a", "summary": "", "description": ""}],
        )
        desc = self._desc(item)
        self.assertNotIn("Purpose:", desc)


class TestFormatJobPurpose(unittest.TestCase):
    """_format_job_purpose() is the single source used by both the
    environ item-level view (single related job) and the per-job-row
    view (job focused in the right-top pane), so it's tested directly."""

    def test_shows_both_when_distinct(self):
        job = {
            "id": "ns::j",
            "purpose": "Check the thing",
            "description": "Usage: do the thing with FOO=bar",
        }
        text = gl._format_job_purpose(job)
        self.assertIn("Purpose    : Check the thing", text)
        self.assertIn("Description: Usage: do the thing with FOO=bar", text)

    def test_omits_description_when_identical_to_purpose(self):
        job = {"id": "ns::j", "purpose": "Same", "description": "Same"}
        text = gl._format_job_purpose(job)
        self.assertEqual(text.count("Same"), 1)
        self.assertNotIn("Description:", text)

    def test_no_text_available(self):
        job = {"id": "ns::j", "purpose": "", "description": ""}
        text = gl._format_job_purpose(job)
        self.assertEqual(text, "(no description available)")


class TestSwitchColumns(unittest.TestCase):
    """_SwitchColumns notifies a callback when left/right arrow keys move
    focus between panes — this is the only route for pane switching,
    since urwid.Columns handles left/right internally before the key
    would ever reach MainLoop's unhandled_input."""

    def _make(self):
        calls = []
        cols = gl._SwitchColumns(
            ["left-widget", "right-widget"],
            on_switch=lambda pos: calls.append(pos),
        )
        return cols, calls

    def test_right_arrow_switches_and_notifies(self):
        cols, calls = self._make()
        cols.keypress((80,), "right")
        self.assertEqual(cols.focus_position, 1)
        self.assertEqual(calls, [1])

    def test_left_arrow_switches_and_notifies(self):
        cols, calls = self._make()
        cols.keypress((80,), "right")
        cols.keypress((80,), "left")
        self.assertEqual(cols.focus_position, 0)
        self.assertEqual(calls, [1, 0])

    def test_unrelated_key_does_not_notify(self):
        cols, calls = self._make()
        cols.keypress((80,), "down")
        self.assertEqual(calls, [])

    def test_no_op_switch_does_not_notify(self):
        """Pressing left while already at position 0 shouldn't fire."""
        cols, calls = self._make()
        cols.keypress((80,), "left")
        self.assertEqual(calls, [])


class _FakeRightWalker(list):
    """Minimal stand-in for urwid.SimpleFocusListWalker's focus API."""

    def __init__(self, items, focus=0):
        super().__init__(items)
        self._focus_idx = focus

    def get_focus(self):
        return self[self._focus_idx], self._focus_idx

    def set_focus(self, i):
        self._focus_idx = i


class TestEnsureRightFocusSelectable(unittest.TestCase):
    """Switching into the right pane must land the cursor on the first
    job row, not the unselectable header/divider — otherwise no focus
    highlight is visible until the user presses up/down once."""

    def _make_screen(self, walker):
        screen = gl.LauncherEditorScreen.__new__(gl.LauncherEditorScreen)
        screen._right_walker = walker
        return screen

    def test_moves_focus_from_header_to_first_job_row(self):
        header = object()
        divider = object()
        row1 = gl._JobRow.__new__(gl._JobRow)
        row2 = gl._JobRow.__new__(gl._JobRow)
        walker = _FakeRightWalker([header, divider, row1, row2], focus=0)
        screen = self._make_screen(walker)

        screen._ensure_right_focus_selectable()

        self.assertEqual(walker._focus_idx, 2)

    def test_leaves_focus_unchanged_when_already_on_job_row(self):
        header = object()
        row1 = gl._JobRow.__new__(gl._JobRow)
        row2 = gl._JobRow.__new__(gl._JobRow)
        walker = _FakeRightWalker([header, row1, row2], focus=2)
        screen = self._make_screen(walker)

        screen._ensure_right_focus_selectable()

        self.assertEqual(walker._focus_idx, 2)

    def test_no_op_when_no_job_rows_present(self):
        header = object()
        divider = object()
        walker = _FakeRightWalker([header, divider], focus=0)
        screen = self._make_screen(walker)

        screen._ensure_right_focus_selectable()  # must not raise

        self.assertEqual(walker._focus_idx, 0)


if __name__ == "__main__":
    unittest.main()
