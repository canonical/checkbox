# checkbox-provider-ce-oem — Agent Instructions

See the root [`AGENTS.md`](../../../AGENTS.md) for global rules and
[`providers/AGENTS.md`](../../../providers/AGENTS.md) for the common
provider structure, `manage.py` usage, and PXU basics.
This file adds what is different for the CE OEM provider.

## What is this provider?

A contrib-area provider with tests for IoT and PC device enablement
(CE OEM QA): GPIO, buzzer, serial/RS485, SocketCAN, MTD, EEPROM, RTC,
crypto accelerators, video codecs, and SoC-specific suites (Genio,
Dragonwing, Renesas RZ, Xilinx, …).

It is shipped as the `checkbox-ce-oem` snap. Snapcraft recipes live in
the sibling [`../checkbox-ce-oem-snap/`](../checkbox-ce-oem-snap/)
directory (one `series_uc*` / `series_classic*` subdirectory per Ubuntu
Core / Classic series). End-user installation and the checkbox config
variables consumed by jobs are documented in [`../README.md`](../README.md).

## Key differences from core providers

- **Namespace**: `com.canonical.contrib` (set in `manage.py`), not
  `com.canonical.certification`. Fully-qualified ids look like
  `com.canonical.contrib::ce-oem-buzzer/input-pcspkr`.
- **Unit format**: all existing units are RFC 822 `.pxu` files; keep new
  units consistent with the feature directory you are editing.
- **CI scope**: `.github/workflows/tox-contrib-provider-ce-oem.yaml`
  runs tox (Python 3.8 and 3.10) only when files under this directory
  change. Keep `bin/` scripts compatible with Python 3.8. The
  `checkbox-ce-oem-daily-*` and `checkbox-ce-oem-edge-builds` workflows
  build the snap.

## Unit layout and naming conventions

One directory per feature under `units/`:

```
units/<feature>/
├── category.pxu     # unit: category, id: <feature> (no prefix)
├── jobs.pxu         # jobs, resource jobs, template units
├── manifest.pxu     # manifest entries (has_<feature>)
├── test-plan.pxu    # test plans, incl. after-suspend variants
└── cases_and_environ.md / README.md   # optional per-feature docs
```

SoC-specific directories (`Genio/`, `dragonwing/`, `rz/`, `Xilinx/`)
group several topics per directory using `<topic>_jobs.pxu`,
`<topic>_test-plan.pxu`, … instead.

- Job ids: `ce-oem-<feature>/<test-name>`; template-generated jobs
  parameterise the last segment (`ce-oem-gpio-buzzer/sound-test-{name}`).
- Resource jobs that parse a config variable into a resource are named
  `ce-oem-<feature>-mapping` and listed in `bootstrap_include`.
- Test plans: `ce-oem-<feature>-full` nests
  `ce-oem-<feature>-manual`, `ce-oem-<feature>-automated`, and their
  `after-suspend-` variants. Jobs that should re-run after suspend get
  `flags: also-after-suspend`.
- Manifest gating: entries are named `has_<feature>`; jobs use
  `imports: from com.canonical.plainbox import manifest` plus
  `requires: manifest.has_<feature> == 'True'`.

To expose a new feature, add its `-manual` / `-automated` plans to the
`nested_part` of the top-level plans in `units/test-plan-ce-oem.pxu`
(and the `test-plan-ce-oem-full-{core,desktop,server}.pxu` variants
where applicable).

## Config variables

Jobs take device-specific input from checkbox config variables declared
with `environ:` (e.g. `GPIO_BUZZER`, `RS485_PORTS`). When adding a job
that needs one, document the variable and its format in the
"Config informations" section of [`../README.md`](../README.md), and
make the job fail with a clear message when the variable is unset.

## Running tests

```bash
cd contrib/checkbox-ce-oem/checkbox-provider-ce-oem
tox -e py310        # what CI runs (plus py38)
# or, inside a venv with checkbox-ng and checkbox-support installed:
./manage.py validate
./manage.py test
```

Notes:

- tox installs `checkbox-ng` and `checkbox-support` from this repo and
  runs `manage.py develop` for the `resource`, `base`,
  `certification-client`, and `certification-server` providers —
  ce-oem units may reference their jobs (e.g.
  `com.canonical.certification::led-indicator-manual`), and a broken
  sibling provider can fail this tox run.
- Python unit tests live in `tests/test_<script>.py`, named after the
  `bin/` script they cover; coverage is measured over `bin/` and
  reported to Codecov under the `contrib-provider-ce-oem` flag. Add a
  matching test module for new `bin/` scripts.
