#!/usr/bin/env python3
"""gen_launcher.py — Interactive TUI launcher generator for ce-oem plans.

Usage:
    python3 gen_launcher.py [--providers-dir PATH] [--output-dir DIR]
                            [--rebuild-cache]
"""

from __future__ import annotations

# §1 Imports + constants
import argparse
import signal
import sys
from dataclasses import dataclass, field
from pathlib import Path

from checkbox_ce_oem_scan import (
    discover_top_level_plans,
    expand_plan,
    expansion_cache_path,
    find_default_repo_roots,
    get_nested_plans,
    get_related_jobs,
    load_expansion_cache,
    load_or_build_cache,
    save_expansion_cache,
)

# §2 Item dataclass


@dataclass
class Item:
    """One manifest entry or environment variable in the launcher editor."""

    kind: str  # "manifest" | "environ"
    key: str  # fully-qualified manifest ID or env-var name
    bare_key: str  # bare manifest id or env-var name
    value: str = ""
    # manifest-only hints
    name: str = ""
    prompt: str = ""
    value_type: str = ""
    # list of {id, summary, description} dicts
    related_jobs: list = field(default_factory=list)


# §3 Data layer


def collect_items(
    full_id: str,
    job_ids: set[str],
    cache: dict,
) -> list[Item]:
    """Build the ordered Item list for the launcher editor.

    Manifest entries come first (sorted by bare key), then environment
    variables (sorted).  Each Item's ``related_jobs`` list is populated.
    """
    jobs = cache["jobs"]
    manifest_entries = cache["manifest_entries"]

    bare_manifests: set[str] = set()
    envs: set[str] = set()
    for jid in job_ids:
        job = jobs.get(jid)
        if not job:
            continue
        bare_manifests.update(job["manifest"])
        envs.update(job["environ"])

    # Hidden manifest keys (bare name starting with "_") are internal and
    # not meant to be filled in by the user, even when a job's `requires:`
    # field references one directly.
    bare_manifests = {b for b in bare_manifests if not b.startswith("_")}

    items: list[Item] = []
    for bare in sorted(bare_manifests):
        detail = manifest_entries.get(bare)
        if detail:
            key = detail["full_id"]
        else:
            # Stage 1: prefer a job with a non-"unknown" provider
            provider = next(
                (
                    jobs[jid]["provider"]
                    for jid in job_ids
                    if jid in jobs
                    and bare in jobs[jid]["manifest"]
                    and jobs[jid]["provider"] != "unknown"
                ),
                "",
            )
            # Stage 2: fall back to the namespace part of the job's full_id
            if not provider:
                for jid in job_ids:
                    if (
                        jid in jobs
                        and bare in jobs[jid]["manifest"]
                        and "::" in jid
                    ):
                        candidate = jid.split("::")[0]
                        if candidate != "unknown":
                            provider = candidate
                            break
            key = f"{provider}::{bare}" if provider else bare
        items.append(
            Item(
                kind="manifest",
                key=key,
                bare_key=bare,
                name=detail.get("name", "") if detail else "",
                prompt=detail.get("prompt", "") if detail else "",
                value_type=(
                    detail.get("value_type", "bool") if detail else "bool"
                ),
                related_jobs=get_related_jobs(
                    "manifest", bare, job_ids, cache
                ),
            )
        )
    for var in sorted(envs):
        items.append(
            Item(
                kind="environ",
                key=var,
                bare_key=var,
                related_jobs=get_related_jobs("environ", var, job_ids, cache),
            )
        )
    return items


# ── §4  Launcher writer ──────────────────────────────────────────────────────


def write_launcher(
    plan_full_id: str,
    items: list[Item],
    output_path: Path,
) -> Path:
    """Write a checkbox launcher ini file to *output_path*.

    The file starts with ``#!/usr/bin/env checkbox-cli-wrapper`` so it can
    be executed directly on a system where checkbox is installed.

    Empty ``Item.value`` fields are written as ``key = `` (blank value) so
    the file can be edited by hand later.  The ``[manifest]`` and
    ``[environment]`` sections are omitted entirely when no relevant items
    exist.
    """
    lines = [
        "#!/usr/bin/env checkbox-cli-wrapper",
        "[launcher]",
        "app_id = com.canonical.contrib:checkbox",
        "launcher_version = 1",
        "stock_reports = text, submission_files, certification",
        "",
        "[test plan]",
        f"unit = {plan_full_id}",
        "forced = yes",
        "",
        "[ui]",
        "type = silent",
    ]

    manifest_items = [i for i in items if i.kind == "manifest"]
    environ_items = [i for i in items if i.kind == "environ"]

    if manifest_items:
        lines += ["", "[manifest]"]
        for item in manifest_items:
            val = item.value if item.value else "false"
            lines.append(f"{item.key} = {val}")

    if environ_items:
        lines += ["", "[environment]"]
        for item in environ_items:
            lines.append(f"{item.key} = {item.value}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def parse_existing_launcher(path: Path) -> dict[str, str]:
    """Read an existing launcher ini file and return a flat {key: value} dict.

    Keys from ``[manifest]`` are stored as-is (e.g.
    ``"com.canonical.contrib::has_gpio"``).  Keys from ``[environment]``
    are stored as-is (e.g. ``"RS485_CONFIG"``).  All other sections are
    ignored.

    Returns an empty dict if the file cannot be read or has no relevant
    sections.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    defaults: dict[str, str] = {}
    current_section: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1].lower()
            continue
        if current_section in ("manifest", "environment") and "=" in stripped:
            k, _, v = stripped.partition("=")
            defaults[k.strip()] = v.strip()
    return defaults


def apply_launcher_defaults(
    items: "list[Item]", defaults: "dict[str, str]"
) -> None:
    """Pre-fill *items* with values loaded from an existing launcher file.

    Matching is tried in order:
    1. Exact full key match (``"com.canonical.contrib::has_gpio"``).
    2. Bare key match — the part after ``::`` (``"has_gpio"``).
    Environ items match by their key name directly.
    """
    if not defaults:
        return
    for item in items:
        if item.key in defaults:
            item.value = defaults[item.key]
        elif item.bare_key in defaults:
            item.value = defaults[item.bare_key]


# ── §5  PALETTE constant ─────────────────────────────────────────────────────

import urwid  # noqa: E402  (import after stdlib block for clarity)

PALETTE = [
    ("header", "white", "dark blue", "bold"),
    ("footer", "light gray", "black", ""),
    ("focus", "black", "light cyan", "bold"),
    ("section", "light cyan", "black", "bold"),
    ("key", "white", "black", ""),
    ("ns_header", "light cyan", "dark blue", "bold"),
    ("value_set", "light green", "black", ""),
    ("value_empty", "dark gray", "black", ""),
    ("bool_on", "black", "light green", "bold"),
    ("bool_off", "dark gray", "black", ""),
    ("hint", "yellow", "black", ""),
    ("desc_text", "yellow", "black", ""),
    ("jobs_hdr", "white", "dark green", "bold"),
    ("job_ns", "dark gray", "black", ""),
    ("job_id", "light blue", "black", "bold"),
    ("job_focus", "black", "light cyan"),
    ("job_sum", "light green", "black", ""),
    ("job_desc", "dark gray", "black", ""),
]


# §6  PlanPickerScreen


class PlanPickerScreen:
    """Full-screen urwid plan-selection UI.

    Displays all *plans* in a scrollable ListBox.  Press ``/`` to activate
    the filter footer (same pattern as checkbox-ng's own selector), type to
    narrow the list, press Enter to apply, Esc to cancel.  Arrow keys
    navigate; Enter selects the focused plan.

    Returns the selected ``(full_id, plan_id, name)`` tuple, or ``None`` if
    the user pressed ``q``/``Q``/``Esc`` without selecting.
    """

    def __init__(self, plans: list[tuple[str, str, str]]):
        self._all = plans
        self._selected: tuple | None = None

    def run(self) -> tuple[str, str, str] | None:
        self._walker = urwid.SimpleFocusListWalker(self._make_rows(self._all))
        listbox = urwid.ListBox(self._walker)

        title = urwid.AttrMap(
            urwid.Text(
                " Checkbox CE-OEM Launcher Generator"
                "   [\u2191\u2193] navigate  [/] filter"
                "  [Enter] pick  [q] quit",
                wrap="clip",
            ),
            "header",
        )
        self._default_footer = urwid.AttrMap(
            urwid.Text(f" {len(self._all)} plans available", wrap="clip"),
            "footer",
        )
        self._filter_edit = urwid.Edit("filter: ")
        self._filter_footer = urwid.AttrMap(self._filter_edit, "footer")
        self._filtering = False

        self._frame = urwid.Frame(
            urwid.AttrMap(listbox, "key"),
            header=title,
            footer=self._default_footer,
        )
        loop = urwid.MainLoop(
            self._frame,
            PALETTE,
            unhandled_input=self._handle_key,
            handle_mouse=False,
        )
        try:
            loop.run()
        except (urwid.ExitMainLoop, KeyboardInterrupt):
            pass
        return self._selected

    # ── row building ──────────────────────────────────────────────

    def _make_rows(self, plans: list[tuple]) -> list:
        rows = []
        for full_id, plan_id, name in plans:
            ns = full_id.split("::")[0] if "::" in full_id else full_id
            label = f"  {plan_id:<52} ({ns})"
            btn = urwid.Button(label)
            urwid.connect_signal(
                btn,
                "click",
                self._on_select,
                user_args=[(full_id, plan_id, name)],
            )
            rows.append(urwid.AttrMap(btn, None, focus_map="focus"))
        return rows

    def _on_select(self, plan: tuple, _btn):
        self._selected = plan
        raise urwid.ExitMainLoop()

    # ── input handling ────────────────────────────────────────────

    def _handle_key(self, key):
        if self._filtering:
            if key == "enter":
                q = self._filter_edit.edit_text.lower()
                filtered = [
                    (fid, pid, nm)
                    for fid, pid, nm in self._all
                    if q in pid.lower() or q in (nm or "").lower()
                ]
                self._walker[:] = self._make_rows(filtered)
                self._frame.contents["footer"] = (
                    self._default_footer,
                    None,
                )
                self._frame.set_focus("body")
                self._filtering = False
            elif key == "esc":
                self._filter_edit.set_edit_text("")
                self._frame.contents["footer"] = (
                    self._default_footer,
                    None,
                )
                self._frame.set_focus("body")
                self._filtering = False
            return

        # normal mode
        if key in ("q", "Q", "esc", "ctrl c"):
            raise urwid.ExitMainLoop()
        if key == "enter":
            w, _ = self._walker.get_focus()
            if w:
                w.original_widget.keypress((80,), "enter")
        elif key == "/":
            self._filter_edit.set_edit_text("")
            self._frame.contents["footer"] = (
                self._filter_footer,
                None,
            )
            self._frame.set_focus("footer")
            self._filtering = True


# §7  ItemRow widget

_KEY_COL_W = 54  # characters reserved for the key column
_KIND_LABEL = {"manifest": "M", "environ": "E"}
# When an ItemRow is focused every named attr must be remapped so the full
# row width (including the key and value spans) turns light cyan.
_ITEM_FOCUS_MAP = {
    None: "focus",
    "key": "focus",
    "value_set": "focus",
    "value_empty": "focus",
    "bool_on": "focus",
    "bool_off": "focus",
}


class _BoolToggleWidget(urwid.Widget):
    """Inline True / False toggle for bool manifest entries.

    Renders as:  <caption>  [▶ true ]   [ false ]
    The selected option is highlighted (``bool_on``); the other is dim
    (``bool_off``).

    Keys: ``←``/``→`` or ``Space`` toggle; ``t``/``T`` → true;
    ``f``/``F`` → false.  ``Enter``/``Tab``/``Esc`` are *not* consumed —
    they bubble up to ``ItemRow``.
    """

    _sizing = frozenset(["flow"])
    _OPTIONS = ("true", "false")

    def __init__(self, caption: list, initial: str):
        self._caption = caption
        self._selected = 1 if initial.lower() == "false" else 0
        super().__init__()

    @property
    def value(self) -> str:
        return self._OPTIONS[self._selected]

    def rows(self, size, focus=False) -> int:  # noqa: D401
        return 1

    def render(self, size, focus=False):
        parts: list = list(self._caption)
        for i, opt in enumerate(self._OPTIONS):
            attr = "bool_on" if i == self._selected else "bool_off"
            parts.append((attr, f"[{opt}]"))
            if i == 0:
                parts.append(("key", "  "))
        return urwid.Text(parts, wrap="clip").render(size, focus=False)

    def selectable(self) -> bool:
        return True

    def keypress(self, size, key):
        if key in ("left", "right", " "):
            self._selected = 1 - self._selected
            self._invalidate()
            return None
        if key in ("t", "T"):
            self._selected = 0
            self._invalidate()
            return None
        if key in ("f", "F"):
            self._selected = 1
            self._invalidate()
            return None
        return key


class ItemRow(urwid.WidgetWrap):
    """A single manifest or environ entry row with toggleable inline edit.

    *Display mode* renders the key in ``('key', …)`` markup and the value
    in ``('value_set', …)`` (green) when non-empty or
    ``('value_empty', …)`` (dim) when blank.

    *Edit mode* for **bool** manifest entries shows a ``_BoolToggleWidget``
    (``←``/``→`` or ``t``/``f`` to pick, ``Enter``/``Tab`` to confirm).
    For all other entries it uses a live ``urwid.Edit`` widget.  Pressing
    ``Esc`` cancels and restores the original value; ``Tab`` or ``Enter``
    saves and exits.

    ``item.value`` is updated in-place on every save so the caller can
    read it after the main loop exits.
    """

    def __init__(self, item: Item):
        self.item = item
        self._editing = False
        self._edit: "urwid.Edit | None" = None
        super().__init__(self._display_widget())

    # ── rendering helpers ─────────────────────────────────────────

    def _key_caption(self) -> list:
        label = _KIND_LABEL.get(self.item.kind, "?")
        # Manifest entries are already grouped under their namespace header,
        # so show only the bare key (e.g. "has_gpio" not "ns::has_gpio").
        key = (
            self.item.bare_key
            if self.item.kind == "manifest"
            else self.item.key
        )
        if len(key) > _KEY_COL_W:
            key = "\u2026" + key[-(_KEY_COL_W - 1) :]  # noqa: E203
        return [("key", f"[{label}] " + key.ljust(_KEY_COL_W) + " = ")]

    def _display_widget(self) -> urwid.Widget:
        val = self.item.value
        val_markup = ("value_set", val) if val else ("value_empty", "")
        return urwid.AttrMap(
            urwid.Text(self._key_caption() + [val_markup]),
            None,
            focus_map=_ITEM_FOCUS_MAP,
        )

    def _edit_widget(self) -> urwid.Widget:
        if self.item.value_type == "bool":
            self._edit = _BoolToggleWidget(
                self._key_caption(), self.item.value
            )
            return urwid.AttrMap(self._edit, "focus")
        self._edit = urwid.Edit(self._key_caption(), self.item.value)
        self._edit.set_edit_pos(len(self.item.value))
        return urwid.AttrMap(self._edit, "focus")

    # ── state transitions ─────────────────────────────────────────

    def activate_edit(self):
        """Switch to inline edit mode, snapshotting the current value."""
        if self._editing:
            return
        self._original_value = self.item.value
        self._editing = True
        self._w = self._edit_widget()

    def deactivate_edit(self):
        """Save buffer and switch back to display mode."""
        if not self._editing:
            return
        self._editing = False
        if self._edit is not None:
            if isinstance(self._edit, _BoolToggleWidget):
                self.item.value = self._edit.value
            else:
                self.item.value = self._edit.edit_text.strip()
        self._w = self._display_widget()

    def cancel_edit(self):
        """Discard changes and restore the original value."""
        if not self._editing:
            return
        self._editing = False
        self.item.value = self._original_value
        self._w = self._display_widget()

    # ── urwid protocol ────────────────────────────────────────────

    def selectable(self) -> bool:
        return True

    def rows(self, size, focus=False) -> int:
        return 1

    def keypress(self, size, key):
        if self._editing:
            if key == "esc":
                self.cancel_edit()
                return None
            if key in ("tab", "enter"):
                self.deactivate_edit()
                return None
            return self._edit.keypress((size[0],), key)
        # display mode
        if key in ("enter", " ", "e"):
            self.activate_edit()
            return None
        return key


class _JobRow(urwid.WidgetWrap):
    """Selectable row showing one related job."""

    def __init__(self, job: dict):
        self._job = job
        jid = job["id"]
        ns, bare = (
            (jid.split("::", 1) + [""])[:2] if "::" in jid else ("", jid)
        )
        summary = job.get("summary", "")
        label = f" {bare}" + (f"  \u2014 {summary}" if summary else "")
        w = urwid.AttrMap(
            # wrap="clip" so long summaries never cause multi-row entries
            urwid.SelectableIcon(label, cursor_position=1, wrap="clip"),
            "job_id",
            "job_focus",
        )
        super().__init__(w)

    @property
    def job(self) -> dict:
        return self._job

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


def _format_job_purpose(job: dict) -> str:
    """Format one related job's ``purpose``/``description`` for display.

    Jobs may define both a short ``_purpose`` and a more detailed
    ``_description``; show both when present rather than letting one
    shadow the other (they're merged into a single "description" field
    elsewhere for the cache summary — here we want the full picture).
    """
    purpose = job.get("purpose", "").strip()
    desc = job.get("description", "").strip()
    if desc == purpose:
        desc = ""  # avoid repeating identical text twice
    if not purpose and not desc:
        return "(no description available)"
    lines = [f"- {job['id']}"]
    if purpose:
        lines.append(f"    Purpose    : {purpose}")
    if desc:
        lines.append(f"    Description: {desc}")
    return "\n".join(lines)


def _build_right_rows(item: "Item | None") -> list:
    """Build the list of widgets for the right pane walker."""
    if item is None:
        return [urwid.Text(" (no selection)", wrap="clip")]
    header = urwid.AttrMap(
        urwid.Text(
            f" Jobs using '{item.bare_key}' ({len(item.related_jobs)})",
            wrap="clip",
        ),
        "jobs_hdr",
    )
    rows: list = [header, urwid.Divider()]
    if not item.related_jobs:
        rows.append(urwid.Text("  (no related jobs found)", wrap="clip"))
    else:
        for job in item.related_jobs:
            rows.append(_JobRow(job))
    return rows


class _SwitchColumns(urwid.Columns):
    """Columns that notifies a callback whenever left/right arrow keys
    move focus between panes.

    Left/right are handled internally by ``urwid.Columns.keypress`` and
    never reach ``MainLoop``'s ``unhandled_input``, so without this hook
    the description pane has no way to know the active pane changed.
    """

    def __init__(self, *args, on_switch=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_switch = on_switch

    def keypress(self, size, key):
        before = self.focus_position
        result = super().keypress(size, key)
        if self.focus_position != before and self._on_switch:
            self._on_switch(self.focus_position)
        return result


# ── §8  LauncherEditorScreen ─────────────────────────────────────────────────


class LauncherEditorScreen:
    """Full-screen urwid editor for filling in launcher manifest/environ.

    Left pane (55 %): scrollable list of ItemRow widgets.
    Right pane (45 %): related jobs for the focused row, always visible.
    Footer: one-line hint (manifest _name/_prompt) + key-bindings bar.
    Press ``s`` to write the launcher files and exit.
    Press ``q`` to quit without saving.
    Press ``b``/``Esc`` to go back to the plan picker.

    When *sub_plans* is provided, pressing ``s`` writes one launcher per
    sub-plan (each with a different ``[test plan] unit``).  Otherwise a
    single launcher is written for *plan_full_id*.
    """

    _BINDINGS = (
        "[←/→] switch pane  [e/Enter/Space] edit  [s] save  [b] back  [q] quit"
    )

    def __init__(
        self,
        plan_full_id: str,
        items: "list[Item]",
        cache: dict,
        output_dir: Path,
        sub_plans: "list[tuple[str, str]] | None" = None,
    ):
        self.plan_full_id = plan_full_id
        self.items = items
        self._cache = cache
        self.output_dir = output_dir
        self.sub_plans = sub_plans or []
        self._saved_paths: list[Path] = []
        self._went_back: bool = False
        self._right_focus: bool = False

    def run(self) -> "list[Path] | None":
        """Run the editor loop; return saved paths list or None if quit."""
        self._item_rows = self._build_item_rows()
        self._walker = urwid.SimpleFocusListWalker(self._item_rows)
        urwid.connect_signal(self._walker, "modified", self._on_focus_changed)
        self._left_lb = urwid.ListBox(self._walker)

        # Right pane — one stable walker + one stable Frame updated in-place.
        # This avoids the urwid "rows, render mismatch" error that occurs when
        # the whole Frame is replaced on every cursor movement.
        self._right_walker = urwid.SimpleFocusListWalker(
            [urwid.Text(" (no selection)", wrap="clip")]
        )
        urwid.connect_signal(
            self._right_walker, "modified", self._on_job_focus_changed
        )
        self._right_lb = urwid.ListBox(self._right_walker)

        # Description area: multi-line, wrap. Shows manifest metadata
        # when an M-row is focused in the left pane, or the selected
        # job's purpose/description when a job is focused in the right.
        self._right_desc = urwid.Text("", wrap="space")
        _desc_lb = urwid.ListBox(urwid.SimpleListWalker([self._right_desc]))

        # Jobs list (top) and description (bottom) split the right pane
        # evenly — both are box widgets, so ``weight`` shares the
        # available rows 50/50 between them.
        self._right_pile = urwid.Pile(
            [
                ("weight", 1, self._right_lb),
                ("pack", urwid.Divider("\u2500")),
                ("weight", 1, urwid.AttrMap(_desc_lb, "desc_text")),
            ]
        )

        # Wrap panes in AttrMap. Right pane uses no background tint,
        # matching the left pane — row-level focus_map (ItemRow /
        # _JobRow) provides the focused-row highlight in both panes.
        self._left_map = urwid.AttrMap(self._left_lb, {None: None})
        self._right_map = urwid.AttrMap(self._right_pile, {None: None})

        cols = _SwitchColumns(
            [
                ("weight", 55, self._left_map),
                ("weight", 45, self._right_map),
            ],
            dividechars=1,
            on_switch=self._on_pane_switch,
        )

        plan_id = self.plan_full_id.split("::")[-1]
        n = len(self.sub_plans)
        suffix = f"  ({n} launchers)" if n else ""
        self._title_text = urwid.Text(
            f"Launcher Generator \u2014 {plan_id}{suffix}", wrap="clip"
        )
        self._status_text = urwid.Text(self._BINDINGS, wrap="clip")

        self._frame = urwid.Frame(
            cols,
            header=urwid.AttrMap(self._title_text, "header"),
            footer=urwid.AttrMap(self._status_text, "footer"),
        )
        self._loop = urwid.MainLoop(
            self._frame,
            PALETTE,
            unhandled_input=self._handle_key,
            handle_mouse=False,
        )
        # Populate right pane with initial selection.
        self._refresh_right_pane()
        try:
            self._loop.run()
        except (urwid.ExitMainLoop, KeyboardInterrupt):
            pass
        return self._saved_paths or None

    @property
    def went_back(self) -> bool:
        """True if the user pressed ``b``/``Esc`` to return to plan picker."""
        return self._went_back

    # ── row building ──────────────────────────────────────────────

    def _build_item_rows(self) -> list:
        rows: list = []
        manifest = [i for i in self.items if i.kind == "manifest"]
        environ = [i for i in self.items if i.kind == "environ"]

        if manifest:
            rows.append(
                urwid.AttrMap(
                    urwid.Text(
                        f" \u2500\u2500 MANIFEST ({len(manifest)} entries)"
                        + " \u2500" * 30,
                        wrap="clip",
                    ),
                    "section",
                )
            )
            # Group by namespace (part before "::", or "(no namespace)")
            ns_groups: dict[str, list] = {}
            for item in manifest:
                ns = item.key.split("::")[0] if "::" in item.key else ""
                ns_groups.setdefault(ns, []).append(item)

            for ns, group in ns_groups.items():
                label = ns if ns else "(no namespace)"
                rows.append(
                    urwid.AttrMap(
                        urwid.Text(
                            f"  \u25b8 {label} ({len(group)})",
                            wrap="clip",
                        ),
                        "ns_header",
                    )
                )
                rows.extend(ItemRow(i) for i in group)

        if environ:
            rows.append(
                urwid.AttrMap(
                    urwid.Text(
                        f" \u2500\u2500 ENVIRONMENT"
                        f" ({len(environ)} entries)" + " \u2500" * 27,
                        wrap="clip",
                    ),
                    "section",
                )
            )
            rows.extend(ItemRow(i) for i in environ)
        return rows

    # ── helpers ───────────────────────────────────────────────────

    def _focused_item(self) -> "Item | None":
        try:
            w, _ = self._walker.get_focus()
            if isinstance(w, ItemRow):
                return w.item
        except Exception:
            pass
        return None

    def _on_focus_changed(self):
        self._refresh_right_pane()

    def _on_job_focus_changed(self):
        """Update description area when right-pane job focus changes."""
        try:
            w, _ = self._right_walker.get_focus()
            if isinstance(w, _JobRow):
                self._right_desc.set_text(_format_job_purpose(w.job))
            else:
                # Focus is on header/divider — show item metadata.
                self._right_desc.set_text(
                    self._desc_for_item(self._focused_item())
                )
        except Exception:
            pass

    def _desc_for_item(self, item: "Item | None") -> str:
        """Return the text to show in the right-pane description area."""
        if item is None:
            return ""
        if item.kind == "manifest":
            parts: list[str] = []
            if item.name:
                parts.append(f"Name   : {item.name}")
            if item.prompt:
                parts.append(f"Prompt : {item.prompt}")
            return "\n".join(parts) if parts else "(no manifest metadata)"
        # environ — the job count is already shown in the right-top pane
        # header, so it isn't repeated here.
        n = len(item.related_jobs)
        if n == 0:
            return "(no related jobs found)"
        if n > 1:
            # Ambiguous: different jobs may use the var for different
            # purposes, so don't guess — point the user at the per-job
            # detail available in the right-top pane instead.
            return (
                "Multiple jobs use this variable — move the cursor to"
                " the right pane above to select a specific job for its"
                " purpose/description."
            )
        # Env vars have no _purpose of their own — surface the single
        # related job's _purpose and _description.
        return _format_job_purpose(item.related_jobs[0])

    def _save(self):
        try:
            if self.sub_plans:
                for sub_full_id, sub_id in self.sub_plans:
                    out = self.output_dir / f"{sub_id}-launcher"
                    write_launcher(sub_full_id, self.items, out)
                    self._saved_paths.append(out)
                self._status_text.set_text(
                    f"Saved {len(self._saved_paths)} launchers"
                    f" to {self.output_dir}"
                )
            else:
                plan_id = self.plan_full_id.split("::")[-1]
                out = self.output_dir / f"{plan_id}-launcher"
                write_launcher(self.plan_full_id, self.items, out)
                self._saved_paths.append(out)
                self._status_text.set_text(f"Saved to {out}")
            raise urwid.ExitMainLoop()
        except OSError as exc:
            self._status_text.set_text(f" ERROR writing file: {exc}")

    # ── right pane ────────────────────────────────────────────────

    def _refresh_right_pane(self):
        """Update right pane content in-place without rebuilding the Frame."""
        item = self._focused_item()
        self._right_walker[:] = _build_right_rows(item)
        self._right_desc.set_text(self._desc_for_item(item))

    def _on_pane_switch(self, position: int):
        """Sync description text after the active pane changes.

        Called both from the explicit ``tab`` binding and from
        ``_SwitchColumns`` (left/right arrow keys), so both routes keep
        the description pane in sync with whichever pane is focused.
        """
        self._right_focus = position == 1
        if self._right_focus:
            self._ensure_right_focus_selectable()
            self._on_job_focus_changed()
        else:
            self._right_desc.set_text(
                self._desc_for_item(self._focused_item())
            )

    def _ensure_right_focus_selectable(self):
        """Move right-pane focus onto the first selectable job row.

        ``ListBox`` doesn't auto-skip non-selectable widgets (the
        header/divider) when it merely gains column focus — it only
        does so on an actual keypress. Without this, the first switch
        into the right pane leaves focus on the unselectable header,
        so no cursor highlight is visible until the user presses
        up/down once.
        """
        try:
            w, _ = self._right_walker.get_focus()
        except Exception:
            return
        if isinstance(w, _JobRow):
            return
        for i, widget in enumerate(self._right_walker):
            if isinstance(widget, _JobRow):
                self._right_walker.set_focus(i)
                return

    # ── input handling ────────────────────────────────────────────

    def _handle_key(self, key):
        if key == "tab":
            body = self._frame.body
            if isinstance(body, urwid.Columns):
                body.focus_position = 0 if self._right_focus else 1
                self._on_pane_switch(body.focus_position)
            return
        if key in ("q", "Q"):
            raise urwid.ExitMainLoop()
        if key in ("b", "B", "esc"):
            self._went_back = True
            raise urwid.ExitMainLoop()
        if key == "ctrl c":
            return  # block Ctrl+C
        if key in ("s", "S"):
            self._save()
            return
        if key == "j":
            self._left_lb.keypress((80, 24), "down")
        elif key == "k":
            self._left_lb.keypress((80, 24), "up")


# §9  main() + entry point


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    # Block Ctrl+C at the OS level — the TUI handles it gracefully via key event.
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--providers-dir",
        metavar="DIR",
        help=(
            "Path to a single checkbox providers root to scan instead of "
            "the default checkbox-ce-oem/checkboxNN snaps (auto-detected "
            "if omitted)"
        ),
    )
    parser.add_argument(
        "--plan-prefix",
        metavar="PREFIX",
        default="ce-oem-iot",
        help=(
            "Top-level test plan id prefix to match, e.g. plans named "
            "'<prefix>-<platform>-<version>' (default: ce-oem-iot)"
        ),
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        default=".",
        help="Directory to write the launcher file (default: current dir)",
    )
    parser.add_argument(
        "--input",
        metavar="LAUNCHER",
        help="Existing launcher file to load as default values for manifest "
        "and environment entries",
    )
    parser.add_argument(
        "--rebuild-cache",
        action="store_true",
        help="Force cache rebuild even if cache is fresh",
    )
    args = parser.parse_args(argv)

    # ── load existing launcher defaults (once, before the loop) ──────
    _input_defaults: dict[str, str] = {}
    if args.input:
        _input_path = Path(args.input)
        if not _input_path.is_file():
            print(
                f"ERROR: --input file not found: {_input_path}",
                file=sys.stderr,
            )
            return 1
        _input_defaults = parse_existing_launcher(_input_path)
        print(
            f"Loaded {len(_input_defaults)} default value(s)"
            f" from {_input_path.name}"
        )

    # ── discover repo root(s) ─────────────────────────────────────
    if args.providers_dir:
        p = Path(args.providers_dir).resolve()
        if not p.is_dir():
            print(
                f"ERROR: --providers-dir path not found: {p}",
                file=sys.stderr,
            )
            return 1
        repo_roots = [p]
    else:
        try:
            repo_roots = find_default_repo_roots()
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    print("Scanning: " + ", ".join(str(p) for p in repo_roots))

    # ── load / build cache ────────────────────────────────────────
    cache = load_or_build_cache(repo_roots, force=args.rebuild_cache)
    if args.rebuild_cache:
        expansion_cache_path(repo_roots).unlink(missing_ok=True)

    # ── plan picker ───────────────────────────────────────────────
    plans = discover_top_level_plans(cache, args.plan_prefix)
    if not plans:
        print(
            f"No top-level plans found matching prefix {args.plan_prefix!r}. "
            "Try --rebuild-cache, --providers-dir, or --plan-prefix.",
            file=sys.stderr,
        )
        return 1

    # ── main loop (re-enter plan picker on "go back") ─────────────
    _job_cache: dict[str, set[str]] = load_expansion_cache(repo_roots)

    while True:
        selected = PlanPickerScreen(plans).run()
        if selected is None:
            print("Aborted.")
            return 1

        full_id, _, _ = selected
        plan_id = full_id.split("::")[-1]

        # ── expand plan + collect items ───────────────────────────
        if full_id in _job_cache:
            job_ids = _job_cache[full_id]
            print(f"\n{plan_id}: {len(job_ids)} jobs (cached)")
        else:
            _SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
            _spin_idx = [0]

            def _progress(plans_visited: int, jobs_found: int) -> None:
                spin = _SPINNER[_spin_idx[0] % len(_SPINNER)]
                _spin_idx[0] += 1
                print(
                    f"\r  {spin} {plans_visited} plans · {jobs_found} jobs",
                    end="",
                    flush=True,
                )

            print(f"\nExpanding {plan_id} …")
            job_ids = expand_plan(full_id, cache, on_progress=_progress)
            print(f"\r  ✓ {len(job_ids)} jobs found          ")
            _job_cache[full_id] = job_ids
            save_expansion_cache(repo_roots, _job_cache)

        items = collect_items(full_id, job_ids, cache)
        apply_launcher_defaults(items, _input_defaults)
        n_man = sum(1 for i in items if i.kind == "manifest")
        n_env = sum(1 for i in items if i.kind == "environ")
        print(f"  {n_man} manifest entries, {n_env} environ variables")

        # ── resolve nested plans ──────────────────────────────────
        sub_plans = get_nested_plans(full_id, cache)
        n_sub = len(sub_plans)
        if n_sub:
            print(
                f"  {n_sub} nested plans → {n_sub} launchers will be written"
            )

        # ── editor ────────────────────────────────────────────────
        output_dir = Path(args.output_dir)
        editor = LauncherEditorScreen(
            full_id, items, cache, output_dir, sub_plans
        )
        paths = editor.run()

        if paths:
            for p in paths:
                print(f"Written: {p}")
            return 0

        if editor.went_back:
            continue  # return to plan picker

        # quit without saving
        return 0


if __name__ == "__main__":
    sys.exit(main())
