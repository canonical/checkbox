# Main Checkbox providers reviewer guidance

In the interest of making the code uniform and maintainable for at least the
Extended Maintenance Period (ESM) that the tests in the main providers usually
outlive, the following describes the code style we follow. There are examples
of deviation from this style in the main providers, but they either have a
motivation or are candidates for refactoring.

This document is not a replacement for automated linting, it is a supplement.

You can violate the following rules but when you do so we expect a strong
motivation to be expressed either in the PR or in comments in the code itself.

# Dependencies

Dependencies are very painful to manage in Checkbox because we support every
Ubuntu version still under ESM. Avoid using dependencies at all costs.

If a dependency can't be avoided:
- Pick a library that is already packaged, it must be available for
Ubuntu 18.04+.
- If a package is not available, creating it/backporting it is possible in our
PPA but you will have to do it.
- If your dependency has a binary dependency, it must be available for all
architectures we support.
- Even if your test isn't supposed to run on older versions of the OS, your
unit tests may still import it. You must mock it, adding the dependency to
tox.ini is not enough.
- Vendoring is an option, but we would prefer to avoid it.
- Dependencies with side effects (like services) are not acceptable.
- Consider the license of the dependency, Checkbox is GPLv3, the dependency
must be compatible.

# Python tests

In the interest of uniformity, we try to limit the APIs that we use.

- Don't use `os.path`, use `pathlib` instead.
- Don't use `%` formatting, use `.format` instead.
- Don't use `os` process management (`system`, `popen` etc.), use `subprocess`.
- Don't use fixed `time.sleep` beside for polling.
- Don't destroy command output if possible.
- Don't wrap `subprocess` calls in your `run_command` function.
- Don't customize `argparse.ArgumentParser` needlessly.
- Don't use regexes.

- Always use `argparse` to parse arguments.
- Always print a command output that doesn't match the form you expect.
- Always favour `subprocess.check_...` functions when launching a command.
- Always `slugify` free form text in resources (or at least, always remove
newlines)
- Always use context managers when doing an action to be undone before exit.

# PlainboXUnits (PXUs)

Checkbox Jobs:
- Don't destructively redirect command output.
- Don't write nested `for` and `if` in the command section.
- Don't write bash scripts, use python instead.
- Don't use `in` in resource expression, prefer adding a new fields.
- Don't use `awk`, limit the use of `sed`. Use python instead.

- Always declare the environment variables your test needs.

Checkbox Templates:
- Don't use jinja.
- Don't template non-`slugify`d fields in IDs.

- Always assume there are spaces in resource fields if they weren't explicitly
removed.
- Always add template fields at the end of the IDs.

Checkbox Test Plans:
- Don't rely on Checkbox fixing your dependencies. If your test needs a
dependency, always add it to the test plan.
- Don't use regex inclusion, use template ids instead.
- Don't assume tests are going to be executed in the order you include them.

- Always verify your modification via `list-bootstrapped` and `expand`
