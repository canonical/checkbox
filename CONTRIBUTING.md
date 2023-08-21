# Contributing to Checkbox

## Introduction

This document provides the information needed to contribute to Checkbox
and its providers.

## General recommendations

Setup your editor of choice to run [autopep8] on save. This helps keep
everything passing [flake8]. The code doesn’t have to be pylint-clean, but
running [pylint] on your code may inform you about issues that could come up
later in the review process.

## Testing

### Hacking on Checkbox and/or its providers

If you want to hack on Checkbox or its providers, one method is to
install everything you need in a Python virtual environment.

Install the required tools:

``` bash
$ sudo apt install git python3-virtualenv
```

Prepare the development environment. If you are an external contributor and
plan on submitting some changes, you will have to [fork the Checkbox repository
first], and clone your own version locally. Otherwise:

``` bash
$ cd ~
$ git clone git@github.com:canonical/checkbox.git
```

Create and activate the Python virtual environment:

``` bash
$ cd ~/checkbox/checkbox-ng
$ ./mk-venv
$ . ~/checkbox-ng/venv/bin/activate
```

Activate the base providers in the virtual environment from within the virtual
environment:

``` bash
(venv) $ cd ~/checkbox/providers/resource/
(venv) $ ./manage.py develop -d $PROVIDERPATH
(venv) $ cd ~/checkbox/providers/base
(venv) $ ./manage.py develop -d $PROVIDERPATH
```

Install the Checkbox support library in the virtual environment:

``` bash
(venv) $ cd ~/checkbox/checkbox-support
(venv) $ python3 -m pip install -e .
```

You should now be able to run checkbox, select a test plan and run it:

``` bash
(venv) $ checkbox-cli
```
### Running/Testing checkbox remote

By default `checkbox-cli` runs locally. If you want to run the [remote version]
you have to activate the `checkbox-cli service` on the Machine under test:

```bash
(venv) # checkbox-cli service
```
> Note: Keep in mind that service has to be run as root and needs the
> virtual env, you may have to re-enable/activate it after a `sudo -s`

Now you can run the remote command to connect to it:
```bash
(venv) $ checkbox-cli remote IP
```

> Note: `service` and `remote` can both run on the same machine.
> in that situation, simply use `127.0.0.1`

### Writing and running unit tests for Checkbox

Writing unit tests for your code is strongly recommended. For functions with an
easily defined input and output, use [doctest]. For more complex units of code
use the standard [unittest library].

### Validate the providers

Ensure the job and test plan definitions follow the correct syntax using
the `validate` command:

    $ ./manage.py validate

### Writing and running unit tests for providers

Run checks for code quality of provider hosted scripts and any unit
tests for providers:

    $ ./manage.py test

### Coverage requirements

In Checkbox we have a coverage requirement for new PRs. This is to ensure
that if anyone has to edit the source in the future we have a reliable way
to determine if the edits are changing the meaning of it. Remember, it may be very
clear to you now, but what about tomorrow? Given this objective, try to
create your tests in a way that captures this spirit, it is not about having
a patch coverage of 80% or 81%. It is better to have a very clean and clear
test collection that covers a little bit less of your patch than a
monstrosity of mocks and patches that are just there to reach the coverage
quota.

To collect your coverage you can run the following:
```
$ python -m pip install coverage pytest pytest-cov
# cd to where your test is
$ python -m coverage run -m pytest .
```
Note that every part of this repository has a `.coveragerc` file, they should
already include anything you may want to see in the report. If something is
missing you can edit it but please, consult with the team before doing so.
Tests are intentionally excluded from the coverage report, this is because
test files tend to inflationate the coverage with no real benefit, so don't
worry if you can not spot yours in the report.

Of course, you may only be interested in the coverage of your patch (for
example, if you change a file that has a very low coverage, we do not want
you to take up the challenge of testing it all if you don't want to!). The
easiest way to get this measurement is to open a new PR and connect it with
your branch. The `codecov.io` Bot should comment on it as soon as the `tox`
job relevant to your change is finished, giving you a handy report. Note
that the bot will tell you what you should improve to meet the requirements,
the constraints are listed in `codecov.yaml` in the repo root.

## Version control recommendations

### Commit title

In general, try to follow [Chris Beams’ recommendations]. In a nutshell:

> -   Limit the length of the title to 50 characters
> -   Begin title with a capital letter
> -   Use the imperative mode (your title should always be able to
>     complete the sentence “If applied, this commit will...”)

### Commit message body

Quoting again from Chris Beams’ article, use the body to explain what
and why vs. how.

Example:

    Run Shellcheck on bin dir scripts

    The test command to manage.py currently looks for python unittests
    in the provider tests/ directory. This change searches the bin/
    directory for files with suffix .sh and automatically generates
    a unittest that runs the shellcheck command on the file.

### Linking a pull request to a GitHub issue

See the [GitHub documentation] for more information.

### Splitting work in separate commits if required

If the changes you provide affect different parts of the project, it is better
to split them in different commits. This helps others when reviewing the
changes, helps investigation later on if a problem is found and usually helps
the original developer to better explain and organize his/her changes.

For example, if you add a new screen to the Checkbox text user interface (TUI)
and then modify Checkbox internals to work with this new screen, it is good to
have one commit for the new screen, and one for the internals changes.

Each commit should be stable, i.e. not introduce regressions or make tests
fail. If two or more commits have to be used together, then they should become
one commit.

### Rework your changes

Sometimes it is necessary to modify your changes (for instance after they have
been reviewed by others). Instead of creating new commits with these new
modifications, it is preferred to use Git features such as [rebase] to rework
your existing commits.

## Merge requests

### General workflow

Follow these steps to make a change to a Checkbox-related project.

1. Check the [GitHub documentation] on how to get started. If you are a
   Checkbox contributor, you can clone the [Checkbox repository] directly; if
you are an external contributor, you will probably have to [fork the
repository] first.

1. If you created a fork, you need to [configure Git to sync your fork with the
   original repository.]

1. Create a branch and switch to it to start working on your changes.  You can
   use any branch name, but it is generally good to include the GitHub issue
number it relates to as well as a quick explanation of what the branch is
about:

        $ git checkout -b 123456-invalid-session-content

1. Work on your changes, test them, iterate, commit your work.

1. Before sending your changes for review, make sure to rebase your work using
   the most up-to-date data from the main repository:

        $ git checkout main
        # If you are a Checkbox contributor:
        $ git fetch origin
        # If you are an external contributor:
        $ git fetch upstream
        # Then, rebase your branch:
        $ git checkout 123456-invalid-session-content
        $ git rebase main
        First, rewinding head to replay your work on top of it...
        Applying: <your commits>

1. [Push your changes] to your GitHub repository.

### Finally...

Once enough people have reviewed and approved your work, it can be merged into
the main branch of the main repository. Ask a member of the Checkbox team to do
this. The branch should be then shortly automatically merged. The pull request
status will then switch to “Merged”.


[autopep8]: https://pypi.org/project/autopep8/
[flake8]: https://flake8.pycqa.org/en/latest/
[pylint]: https://www.pylint.org/
[fork the Checkbox repository first]: https://docs.github.com/en/get-started/quickstart/fork-a-repo
[remote version]: https://checkbox.readthedocs.io/en/latest/remote.html
[doctest]: https://docs.python.org/3/library/doctest.html
[unittest library]: https://docs.python.org/3/library/unittest.html
[Chris Beams’ recommendations]: https://chris.beams.io/posts/git-commit/
[GitHub documentation]: https://docs.github.com/en/issues/tracking-your-work-with-issues/linking-a-pull-request-to-an-issue
[rebase]: https://git-scm.com/book/en/v2/Git-Tools-Rewriting-History
[GitHub documentation]: https://docs.github.com
[Checkbox repository]: https://github.com/canonical/checkbox
[fork the repository]: https://docs.github.com/en/get-started/quickstart/fork-a-repo
[configure Git to sync your fork with the original repository.]: https://docs.github.com/en/get-started/quickstart/fork-a-repo#configuring-git-to-sync-your-fork-with-the-original-repository
[Push your changes]: https://docs.github.com/en/get-started/using-git/pushing-commits-to-a-remote-repository
