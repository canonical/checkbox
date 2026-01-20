<!-- GitHub Copilot / AI agent instructions for contributors working on Checkbox -->

This repository contains several cooperating components: the core app (`checkbox-ng`),
the `providers/` (provider implementations and builders), helper libraries (`checkbox-support`),
packaging/snaps (`checkbox-snap`, `checkbox-core-snap`), and tools (`metabox`, `providers/*`).

Keep guidance short and actionable. If you change behavior, link to a file or test that demonstrates it.

- Big picture
  - `checkbox-ng/` is the Python core application (CLI entrypoint `checkbox-cli`). See `checkbox-ng/pyproject.toml` for entry-points and deps.
  - `providers/` contains provider implementations; providers expose plainbox entry-points and are validated/built with the provider `manage.py` scripts (e.g. `providers/resource/manage.py`).
    - Main providers: `base` (core device tests), `resource` (job requirements/resources), `certification-client`, `certification-server`, `sru`, `tpm2`, `gpgpu`, `docker`, `genio`, `iiotg`, `tutorial`.
    - Provider anatomy: `manage.py` (setup/build/test/validate), `bin/` (test scripts), `units/` (`.pxu` job/template/test-plan definitions), `tests/` (unit tests), `pyproject.toml`, `tox.ini`.
  - Packaging is handled with snaps under `checkbox-snap/` and `checkbox-core-snap/`.

- Typical developer workflow (repeatable and discoverable)
  1. Create a development virtualenv from `checkbox-ng`:
     - cd into `checkbox-ng` and run `./mk-venv` then `source venv/bin/activate`.
  2. Enable provider development and build helpers from inside the provider dir:
     - `(venv) $ ./manage.py develop -d $PROVIDERPATH` and `(venv) $ ./manage.py build` (see `CONTRIBUTING.md`).
  3. Install support libs for live edits: `(venv) $ cd checkbox-support && python -m pip install -e .`.
  4. Run the app with `checkbox-cli` (installer script via `pyproject` entry-points).

- Tests and CI
  - Provider tests and checks: run `./manage.py test` from a provider directory (supports `-k` to select tests). See `CONTRIBUTING.md`.
  - `checkbox-ng` runs under `tox` (`checkbox-ng/tox.ini`) which installs the package, validates providers and runs `pytest` + `coverage`.
  - Coverage and Codecov are used; see `codecov.yml` and `CONTRIBUTING.md` for expectations.

- Project-specific conventions to follow
  - Black formatting is enforced (line-length = 79). See `checkbox-ng/pyproject.toml` and `CONTRIBUTING.md`.
  - Versioning: `setuptools_scm` is used (`checkbox-ng/setup.py`). Some build scripts set `SETUPTOOLS_SCM_PRETEND_VERSION` — be careful when changing version-related logic.
  - Commit signing: signed commits are required by CI (see `CONTRIBUTING.md`).
  - Provider code style: see `providers/README.md` for comprehensive guidelines. Key rules:
    - Python: use `pathlib` (not `os.path`), `.format()` (not `%`), `subprocess` (not `os.system`), `argparse` for CLI, avoid regexes, always slugify resource fields.
    - PXU jobs: avoid nested bash loops/ifs (use Python scripts in `bin/`), don't destructively redirect output, declare environment variables explicitly.
    - PXU templates: no Jinja, template fields go at end of IDs, assume spaces in resource fields unless explicitly removed.
    - Dependencies: avoid at all costs; must support Ubuntu 18.04+ ESM and all architectures.

- Integration points and files to inspect when changing behavior
  - CLI / entrypoints: `checkbox-ng/pyproject.toml` (scripts/entry-points such as `checkbox-cli`).
  - Provider validation/build: `providers/*/*/manage.py` (used by `tox` and `./manage.py` helpers).
  - Snap packaging: `checkbox-snap/` and `checkbox-core-snap/` directories.
  - Tests: `checkbox-ng/checkbox_ng/test_*.py` and `providers/*/*/tests` — run with `pytest`/`./manage.py test`/`tox`.

- Examples (copyable snippets)
  - Create dev env and run CLI
    - cd checkbox/checkbox-ng
    - ./mk-venv
    - source venv/bin/activate
    - python -m pip install -e ../checkbox-support
    - checkbox-cli

  - Run provider tests
    - cd checkbox/providers/resource
    - ./manage.py test

  - Validate provider syntax and build executables
    - cd checkbox/providers/base
    - ./manage.py validate
    - ./manage.py build

  - Provider anatomy (example: `providers/base/`)
    - `manage.py` — setup/build/test/validate commands
    - `bin/` — test scripts (Python/shell) referenced by jobs
    - `units/` — `.pxu` files defining jobs, templates, test-plans, categories
    - `tests/` — unit tests for `bin/` scripts
    - `pyproject.toml`, `tox.ini`, `.coveragerc` — config for testing/coverage
