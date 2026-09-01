# Claude — Checkbox repository

Read [`AGENTS.md`](AGENTS.md) first. It contains the authoritative global
rules for this monorepo: component map, Python/shell conventions, commit
requirements, and PR rules.

When working inside a specific component, also read the nearest `AGENTS.md`
in that subdirectory (e.g. `checkbox-ng/AGENTS.md`). Local rules take
precedence over root rules for that component.

## Claude-specific notes

- Always disable pagers when running shell commands (`git --no-pager`,
  `| cat`, `PAGER=cat`, etc.) to avoid interactive prompts.
- Prefer `tox` for running tests; it handles virtual-environment isolation.
- Do not install packages globally; use the component's virtual environment.
- Signed commits are required — do not amend or rebase in a way that loses
  signatures unless you immediately re-sign.
- When unsure whether a change is `(Breaking)`, check AGENTS.md and ask
  rather than guessing.
