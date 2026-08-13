# gen_launcher.py — Interactive Launcher Generator

A terminal UI tool that scans checkbox CE-OEM `.pxu` test-plan files,
lets you pick a top-level `ce-oem` test plan, fill in manifest and
environment values interactively, and writes a ready-to-use launcher file.

## Requirements

- Python 3.10+
- [`urwid`](https://urwid.org/) ≥ 1.1.1 (already a `checkbox-ng` dependency)
- By default the script scans installed checkbox snaps for full test
  plan coverage: `/snap/checkbox-ce-oem/current` and every
  `/snap/checkboxNN/current` (NN = digits, e.g. 20/22/24/26). If no
  such snap is installed, it falls back to auto-detecting the checkbox
  checkout root from its own location.
- Provider namespaces are resolved from either a `manage.py` file
  (source checkouts) or a `*.provider` ini file (installed/snap
  providers, written by `manage.py install`) — whichever is found
  first walking up from the `.pxu` file. This is what lets namespace
  grouping (e.g. `▸ com.canonical.contrib (12)`) work correctly when
  scanning snaps, instead of falling back to `▸ unknown`.
- Scanning/discovery logic lives in `checkbox_ce_oem_scan.py`, which has
  **no `urwid` dependency** and can be imported or run standalone (e.g. in
  CI) without a TUI environment. `gen_launcher.py` imports its scanning
  primitives from that module and adds only the interactive `urwid` layer
  on top.

## Usage

```
python3 gen_launcher.py [--providers-dir DIR] [--output-dir DIR]
                        [--input LAUNCHER] [--rebuild-cache]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--providers-dir DIR` | auto-detect (checkbox-ce-oem + checkboxNN snaps, or checkout root) | Path to a single checkbox providers root to scan instead of the default snaps |
| `--plan-prefix PREFIX` | `ce-oem-iot` | Top-level test plan id prefix to match, e.g. plans named `<prefix>-<platform>-<version>` |
| `--output-dir DIR` | `.` (current directory) | Directory where the generated launcher file is written |
| `--input LAUNCHER` | _(none)_ | Existing launcher file whose `[manifest]` and `[environment]` values are pre-loaded as defaults |
| `--rebuild-cache` | off | Force a full rescan of all `.pxu` files, ignoring any cached data |

The script is also executable directly:

```
./gen_launcher.py
./gen_launcher.py --input path/to/existing-launcher
```

## Workflow

1. **Plan picker** — a scrollable list of top-level test plans (id matching
   `<plan-prefix>-<platform>-<version>`, e.g. `ce-oem-iot-desktop-24-04`;
   `--plan-prefix` defaults to `ce-oem-iot`) is shown. Press `/` to filter
   by name, Enter to select.

2. **Launcher editor** — the screen is split into two panes.

   - **Left pane (55 %)** lists every manifest variable and environment
     variable required by the selected plan.  Manifest entries are grouped
     under a `── MANIFEST` section header and further sub-grouped by
     provider namespace (e.g. `▸ com.canonical.contrib (12)`); each row
     shows only the **bare key** (e.g. `has_gpio`) — the namespace is
     already visible in the group header above it. Environment variables
     follow under a `── ENVIRONMENT` section header.  Navigate with arrow
     keys; the focused row is highlighted across the full row width.  Press
     `Enter`, `Space`, or `e` to edit a value inline.

     **Bool manifest entries** (all current `manifest entry` units use
     `value-type: bool`) show an inline toggle instead of a text field:

     ```
     [M] has_gpio = [true]  [false]
     ```

     Use `←` / `→` or `Space` to switch between options, `t`/`T` to jump
     to `true`, `f`/`F` to jump to `false`, then `Enter` or `Tab` to
     confirm.  Free-form text input is not possible, preventing type errors.

   - **Right pane (45 %)** shows all jobs across the provider database that
     reference the currently focused manifest key or environment variable.
     It is split evenly top/bottom between the job list and a description
     area:
     - For a manifest entry: the bottom pane shows its human-readable
       **Name** and **Prompt** (from the `manifest entry` unit in the
       PXU files).
     - For an environment variable used by exactly **one** job: its
       **Purpose** (from `_purpose`) and, if different, **Description**
       (from `_description`).
     - For an environment variable used by **more than one** job: a hint
       to move the cursor into the right pane and select a specific job
       row, since different jobs may use the variable for different
       purposes.
     - For a job selected in the right-top pane: that job's own
       Purpose/Description.

     Press `Tab`, or `←`/`→` to move keyboard focus between the left and
     right panes and navigate the job list; the description area updates
     immediately regardless of which key was used to switch.

3. **Save** — press `s` to write the launcher files and exit, `b`/`Esc` to
   go back to the plan picker, or `q` to quit without saving.

   When the selected top-level plan has a `nested_part`, pressing `s`
   writes **one launcher per nested plan** (e.g.
   `ce-oem-iot-ubuntucore-26-crypto-launcher`,
   `ce-oem-iot-ubuntucore-26-gpio-launcher`, …).  Each launcher's
   `[test plan] unit` is set to the corresponding nested plan ID.  The
   manifest and environment values filled in the editor are shared across
   all generated launchers.  The number of launchers to be written is
   shown in the editor title bar.

### Key bindings

#### Plan picker

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate plans |
| `/` | Filter plans by substring (Enter applies, Esc cancels) |
| `Enter` | Select plan and open editor |
| `q` / `Esc` | Quit |

#### Launcher editor (left pane)

| Key | Action |
|-----|--------|
| `↑` / `↓` | Move between items |
| `Enter` / `Space` / `e` | Edit value inline |
| `Enter` (in edit mode) | Commit new value |
| `Esc` (in edit mode) | Cancel edit (restore original value) |
| `←` / `→` / `Space` (bool toggle) | Switch between `true` and `false` |
| `t` / `T` (bool toggle) | Jump to `true` |
| `f` / `F` (bool toggle) | Jump to `false` |
| `s` | Save launcher file and exit |
| `b` / `Esc` | Go back to plan picker |
| `q` | Quit without saving |

#### Right pane (jobs list)

| Key | Action |
|-----|--------|
| `Tab` / `←` / `→` | Switch focus between left and right panes |
| `↑` / `↓` | Navigate related jobs |

## Pre-loading an existing launcher

Pass `--input` to seed the editor with values from a previously generated
launcher file:

```
./gen_launcher.py --input ce-oem-iot-ubuntucore-26-launcher
```

The tool reads the `[manifest]` and `[environment]` sections of the input
file and pre-fills every matching item in the editor.  Matching is tried
first by full namespaced key (`com.canonical.contrib::has_gpio`) and then
by bare key (`has_gpio`), so launchers from slightly different namespace
contexts still load correctly.  The same defaults apply across all plan
selections in a single session.

## What counts as a top-level plan

Top-level plans are discovered by matching a test plan's **bare id**
(not its filename) against a prefix pattern, via
`discover_top_level_plans(cache, plan_prefix)` in
`checkbox_ce_oem_scan.py`:

```
^<plan-prefix>-(?P<platform>[a-z]+)-(?P<version>\d+)(?:-04)?$
```

`plan_prefix` defaults to `ce-oem-iot` and can be overridden with
`--plan-prefix` (see the flag tables above/below). Any plan across the
scanned provider roots whose id matches this pattern is shown in the
picker — there is no dependency on specific PXU filenames or on
`nested_part` structure.

This currently yields plans such as `ce-oem-iot-ubuntucore-26`,
`ce-oem-iot-server-26-04`, `ce-oem-iot-desktop-26-04`, and their older
Ubuntu release counterparts.

When more than one provider repo root is scanned (e.g. both
`checkbox-ce-oem` and a `checkboxNN` snap), a plan/job/manifest id seen
in more than one root keeps the version from the first root in scan
order (`checkbox-ce-oem` first, then `checkboxNN` snaps).

## Hidden manifest entries

Manifest entries whose bare id starts with `_` (e.g. `_internal_flag`)
are internal/derived and are excluded from the editor and the written
launcher file — there is nothing for the user to fill in for them.

## Output format

The generated file name is `<plan-id>-launcher` with no extension
(e.g. `ce-oem-iot-ubuntucore-26-launcher`) and starts with a shebang so it
can be executed directly on a system with checkbox installed:

```ini
#!/usr/bin/env checkbox-cli-wrapper
[launcher]
app_id = com.canonical.contrib:checkbox
launcher_version = 1
stock_reports = text, submission_files, certification

[test plan]
unit = com.canonical.contrib::ce-oem-iot-ubuntucore-26
forced = yes

[ui]
type = silent

[manifest]
com.canonical.contrib::has_gpio = True
com.canonical.contrib::has_spi = false
com.canonical.certification::has_edac_module = false

[environment]
RS485_CONFIG = /dev/ttyS0
OTG =
```

### Manifest defaults

- Manifest entries use a **True / False toggle** — free-form text input is
  not allowed, so type errors are impossible.
- Entries **left at their initial toggle state** (`false`) are written as
  `key = false`.
- Entries toggled to `true` are written as `key = true`.

### Environment variables

Only variables explicitly declared in a job's `environ:` field are
collected. Variables referenced implicitly in a job's `command:` shell
script are intentionally excluded to avoid noise.

OS/Checkbox-runtime-reserved vars are also excluded, even if declared in
`environ:` — they're never meant to be set by an ODM integrator (and
manifest/environment values here are simple strings, so surfacing them
just invites confusion). This is an exact-name list
(`XDG_CURRENT_DESKTOP`, `XDG_SESSION_TYPE`, `PLAINBOX_PROVIDER_DATA`,
`PLAINBOX_SESSION_SHARE`) plus prefix matching (`XDG_*`, `PLAINBOX_*`)
so future vars in the same families are auto-excluded without code
changes. See `_is_reserved_environ()` in `checkbox_ce_oem_scan.py`.

## Ctrl+C

Ctrl+C is intentionally blocked while the TUI is running. Use `q` to quit
or `b`/`Esc` to go back to the plan picker.

## Caching

### PXU cache

On first run the script scans all `.pxu` provider files under every
scanned repo root (e.g. both `checkbox-ce-oem` and a `checkboxNN` snap)
and writes a JSON cache to `/tmp/gen_launcher_<hash8>.json` (hash of the
combined, sorted repo root paths).  The file is **kept between runs** so
cold start is fast.  The cache is automatically invalidated and rebuilt
whenever:

- any `.pxu` file under any scanned repo root is newer than the cache
  file,
- `--rebuild-cache` is passed on the command line, or
- the cache was written by an older version of the script (version stamp
  mismatch).

### Plan-expansion cache

Expanding a test plan (resolving all `include` / `nested_part` patterns to
a concrete list of job IDs) can take a few seconds for large plans.  The
result is persisted to `/tmp/gen_launcher_<hash8>_expansions.json` so that
**subsequent runs in the same boot session skip the expansion entirely**.

The expansion cache is automatically invalidated when:

- the PXU cache is rebuilt (any `.pxu` file changed), or
- `--rebuild-cache` is passed on the command line.

Both cache files live in `/tmp`, so they are cleared automatically on the
next reboot.

Because both cache file names are derived from the set of scanned repo
root paths, different repo-root combinations each get their own cache
files and never interfere with each other.

Within a single session, test-plan expansions are also cached in memory —
going back to the plan picker and selecting the same plan reuses the prior
expansion without any file I/O.

## Running the tests

```
python3 -m unittest test_checkbox_ce_oem_scan test_gen_launcher -v
```

101 unit tests total, split across two files:

- `test_checkbox_ce_oem_scan.py` — the data layer (PXU parsing, cache
  schema, plan expansion, glob matching, manifest/environ extraction,
  reserved-environ-var filtering, default repo-root discovery, hidden
  manifest filtering, multi-root scanning, top-level plan discovery,
  cache version invalidation, `dump_inventory_json`, and the standalone
  CLI's `main()`).
- `test_gen_launcher.py` — the TUI layer (launcher file format,
  existing-launcher import, `ItemRow` edit-mode state transitions, job
  purpose/description formatting, and right-pane focus-switching, `Tab`
  and arrow keys, including auto-focusing the first job row).

## checkbox_ce_oem_scan.py — JSON inventory export

`checkbox_ce_oem_scan.py` is the scanning/discovery core used by
`gen_launcher.py`'s TUI. It also has its own standalone CLI for
non-interactive use (e.g. CI), which dumps one JSON inventory file per
discovered top-level-plan version:

```
python3 checkbox_ce_oem_scan.py --providers-dir DIR --output-dir OUT/ \
    [--plan-prefix PREFIX] [--checkbox-repository URL] \
    [--checkbox-commit SHA] [--rebuild-cache]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--providers-dir DIR` | _(required)_ | Path to a checkbox providers root to scan |
| `--output-dir DIR` | _(required)_ | Directory to write one `{version}.json` file per discovered version |
| `--plan-prefix PREFIX` | `ce-oem-iot` | Top-level test plan id prefix to match |
| `--checkbox-repository URL` | `""` | Value recorded as `checkbox_repository` in each dumped JSON |
| `--checkbox-commit SHA` | `""` | Value recorded as `checkbox_commit` in each dumped JSON |
| `--rebuild-cache` | off | Force a full rescan of all `.pxu` files, ignoring any cached data |

Each `{version}.json` file's schema (`version`, `plan_full_ids`,
`checkbox_repository`, `checkbox_commit`, `manifests`, `environments`) is
intentionally aligned field-for-field with
`odm_program_documentation`'s `Inventory` schema, so
a future consumer of this output does not need an adapter layer. There is
currently no automated integration between the two tools — this CLI is a
standalone, independently usable export.

**Performance note:** unlike `gen_launcher.py`'s TUI (which caches plan
expansions via `load_expansion_cache`/`save_expansion_cache`), this CLI
re-expands every top-level plan from scratch on each invocation.
Expansion is `O(patterns × total_jobs)` per plan with no memoization
across nested sub-plans; on a ~1500-job provider corpus this measured
~0.5-3s per top-level plan, so a run covering many versions/platforms can
take tens of seconds. This is acceptable when the CLI runs once per CI
workflow trigger. If it starts running more frequently (e.g. on every
push, or interactively in a loop), wire in
`load_expansion_cache`/`save_expansion_cache` around the `expand_plan`
calls in `main()` the same way `gen_launcher.py`'s `main()` does.
