# Checkbox monorepo — Agent Instructions

## What is this repository?

[Checkbox](https://checkbox.readthedocs.io) is a hardware certification and
testing framework for Ubuntu Linux, maintained by Canonical. It validates
device compatibility and generates test reports (HTML, JSON, JUnit, text).

This is a **monorepo**. Each top-level directory is an independently
deployable component with its own packaging, tests, and release pipeline.

---

## Component map

| Directory | What it is |
|---|---|
| `checkbox-ng/` | Core CLI application and the `plainbox` engine |
| `checkbox-support/` | Python helpers and parsers used by checkbox-ng and providers |
| `providers/` | Test-plan definitions (PXU units + shell/Python scripts) |
| `checkbox-core-snap/` | Snapcraft recipe for the Checkbox core snap |
| `checkbox-snap/` | Snapcraft recipe for the Checkbox test-runner snap |
| `metabox/` | Integration-testing tool using LXD containers / VMs |
| `contrib/` | Community-maintained providers (OEM QA, DSS, GFX, …) |
| `docs/` | Sphinx documentation deployed to Read the Docs |
| `submission-schema/` | JSON schema for Checkbox test-report submissions |
| `tools/` | Release tooling and miscellaneous scripts |

When working in a component, also read the `AGENTS.md` file inside that
directory (if it exists) for local context, commands, and constraints.

---

## Global conventions

### Python style

- Formatter: **black**, `--line-length 79`, excluding `vendor/` directories.
  All Python files must pass `black --check` before merging.
- Linter: **flake8** (run via `manage.py test` in providers, or as part of
  tox in other components).
- Type hints are not enforced everywhere, but are welcome for new code.
- Use `doctest` for simple, well-defined input/output functions.
- Use the standard `unittest` library for more complex tests.

### Shell scripts

- All shell scripts in `bin/` directories are checked with **ShellCheck**.
  New scripts must pass ShellCheck before merging.

### Documentation

- Docs live in `docs/` and are written in **reStructuredText**.
- Wrap prose at **80 characters**.
- Follow the [Canonical documentation style guide](https://docs.ubuntu.com/styleguide/en).

### Test coverage

- New code must come with tests. Coverage is tracked via
  [Codecov](https://codecov.io) and the bot comments on every PR.
- Do not add tests that chase coverage numbers mechanically; test behaviour.

---

## Version control rules

### Commit title

- Maximum **50 characters**.
- Start with a **capital letter**.
- Use the **imperative mood** ("Add support for X", not "Added support for X").
- No trailing full stop.

### Commit body

Explain *what* and *why*, not *how*. Wrap at 72 characters.

### Signed commits (required)

All commits must be GPG-signed. CI will reject unsigned commits on
Canonical-operated self-hosted runners.

```bash
git config --global user.signingkey <your-key-id>
git config --global commit.gpgSign true
```

To retroactively sign commits on a feature branch:

```bash
git rebase --exec 'git commit --amend --no-edit -n -S' -i main
```

---

## Pull request rules

### Title format (enforced by CI)

Every PR title must end with one of the following traceability markers
(case-insensitive):

| Marker | When to use |
|---|---|
| `(Infra)` | Docs, comments, GitHub Actions, metabox-only changes |
| `(BugFix)` | Fixes a bug |
| `(New)` | New backward-compatible feature, test, test plan, or test inclusion |
| `(Breaking)` | Breaks backward compatibility (see below) |

**Breaking** includes: any public API change to `checkbox-ng` or
`checkbox-support`, changes to PXU grammar or field requirements, and
breaking dependency changes in snaps. Provider-only changes cannot be
`(Breaking)`.

### PR template requirements

Fill in all sections of `.github/pull_request_template.md`:

- **Description** — problem solved + implementation approach + data-format
  changes.
- **Resolved issues** — link every related GitHub / Jira issue.
- **Documentation** — confirm docs are up to date.
- **Tests** — list what was tested and on what platform.

### SRU test plans

If a PR modifies `com.canonical.certification::sru` or
`com.canonical.certification::sru-server`, the PR description **must**
include the corresponding warning header:

```
## WARNING: This modifies com.canonical.certification::sru
```

CI checks for this header automatically.

### Submission schema

If a change affects the Checkbox test-report submission format, update
`submission-schema/schema.json`.

---

## How to choose which AGENTS.md to follow

1. Read this root file first for global rules.
2. `cd` into the component directory you are changing.
3. If an `AGENTS.md` exists there, read it for local overrides and commands.
4. Local rules take precedence over root rules for that component.

Component AGENTS.md files exist in:

- `checkbox-ng/`
- `checkbox-support/`
- `providers/`
- `metabox/`
