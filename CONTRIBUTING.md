# Contributing to Checkbox

## Introduction

This document provides the information needed to contribute to Checkbox,
its providers and its documentation.

## General recommendations

- Setup your editor of choice to run [autopep8] on save. This helps keep
everything passing [flake8].
- The code doesn’t have to be pylint-clean, but
running [pylint] on your code may inform you about issues that could come up
later in the review process.

## Testing

### Install Checkbox and its providers in a virtual environment

If you want to hack on Checkbox or its providers, one method is to
install everything you need in a Python virtual environment.

Install the required tools:

    $ sudo apt install git python3-virtualenv

Prepare the development environment. If you are an external contributor and
plan on submitting some changes, you will have to [fork the Checkbox repository
first], and clone your own version locally. Otherwise:

    $ cd ~
    $ git clone git@github.com:canonical/checkbox.git

Create and activate the Python virtual environment:

    $ cd ~/checkbox/checkbox-ng
    $ ./mk-venv
    $ . ~/checkbox/checkbox-ng/venv/bin/activate

Activate the base providers in the virtual environment from within the virtual
environment:

    (venv) $ cd ~/checkbox/providers/resource/
    (venv) $ ./manage.py develop -d $PROVIDERPATH
    (venv) $ cd ~/checkbox/providers/base
    (venv) $ ./manage.py develop -d $PROVIDERPATH

Install the Checkbox support library in the virtual environment:

    (venv) $ cd ~/checkbox/checkbox-support
    (venv) $ python3 -m pip install -e .

You should now be able to run checkbox, select a test plan and run it:

    (venv) $ checkbox-cli

### Running/Testing Checkbox Remote

By default `checkbox-cli` runs locally. If you want to run the [remote version]
you have to activate the `checkbox-cli run-agent` on the Machine under test:

    (venv) # checkbox-cli run-agent

> Note: Keep in mind that run-agent has to be run as root and needs the
> virtual env, you may have to re-enable/activate it after a `sudo -s`

Now you can run the control command to connect to it:

    (venv) $ checkbox-cli control IP

> Note: `run-agent` and `control` can both run on the same machine.
> in that situation, simply use `127.0.0.1` as the `IP`.

### Writing and running unit tests for Checkbox

Writing unit tests for your code is required. For functions with an easily
defined input and output, use [doctest]. For more complex units of code, use
the standard [unittest library].

### Validate the providers

Ensure the jobs and test plans definitions follow the correct syntax using
the `validate` command. From one of the providers directory:

    (venv) $ ./manage.py validate

### Writing and running unit tests for providers

Run checks for code quality of provider hosted scripts and any unit
tests for providers. From one of the providers directory:

    (venv) $ ./manage.py test

Under the hood, this command will

- check Shell scripts using [ShellCheck]
- check Python code quality using [flake8]
- run all the Python unit tests

You can run each part separately. See `./manage.py test -h` for more
information.

If you only want to run one test script from the test suite, you have to
point the `PYTHONPATH` environment variable to the provider's `bin/` directory,
then go to the `tests/` directory and run the unit tests for your test file:

    (venv) $ PYTHONPATH=~/checkbox/providers/base/bin python -m unittest <your_test_file.py>

### Coverage

In Checkbox we have a coverage requirement for new PRs. This is to ensure
that new contributions do not add source paths that are not explored in testing
and therefore easy to break down the line with any change.

#### Collecting Coverage

To collect your coverage and generate a coverage report, run the following:

    $ python -m pip install coverage
    # cd to the provider you want to test
    $ python -m coverage run manage.py test -u
    $ python -m coverage html

You will get a nice HTML report you can use to visualize the test coverage for
all the scripts in the provider.

Note that every part of this repository has a `.coveragerc` file, they should
already include anything you may want to see in the report. If something is
missing you can edit it but please, consult with the team before doing so.
Tests are intentionally excluded from the coverage report, this is because
test files tend to inflate the coverage with no real benefit, so don't
worry if you can not spot yours in the report.

Of course, you may only be interested in the coverage of your patch (for
example, if you change a file that has a very low coverage, we do not want
you to take up the challenge of testing it all if you don't want to!). The
easiest way to get this measurement is to open a new PR and connect it with
your branch. The `codecov.io` Bot should comment on it as soon as the `tox`
job relevant to your change is finished, giving you a handy report. Note
that the bot will tell you what you should improve to meet the requirements,
the constraints are listed in `codecov.yaml` in the repo root.

#### Effective coverage

Getting coverage right is not about having all lines in a source file executed.
Coverage is more of a proxy measure of how much of your code behaviour does
your test actually execute.

Consider the following:

```python
def get_mod_status(a : int, b : int) -> str:
    try:
        if a % b == 0:
            return "A is divisible by B"
        return "A is not divisible by B"
    except ZeroDivisionError:
        return "B is 0"
    except ValueError:
        return "Unknown error"
```

To get 100% code coverage you may write the following tests:

```python
def test_nominal_ok_0(): assert get_mod_status(10, 2) == "A is divisible by B"
def test_nominal_ok_1(): assert get_mod_status(10, 3) == "A is not divisible by B"
def test_error_0(): assert get_mod_status(10, 0) == "B is 0"

def test_error_1():
    class error_mod:
        def __mod__(self, other):
            raise ValueError("Unknown error")
    assert get_mod_status(error_mod(), 10) == "Unknown error"
```

This is not a very good test suite but we have reached 100% coverage. Notice
that most of the function above is easily tested by the first
three tests and covering the last two lines takes quite a lot of complexity.
This is already an indicator that it may not be worth covering them.
Now consider the fact that `a % b` is equivalent to
`a - (a // b * b)` so they are interchangeable, but if we swap them in the
implementation, the last test fails. What went wrong here is that to reach
100% coverage we are giving up on testing the functionality and we are
writing tests that mindlessly follow specific code path.

Wrapping up, while preparing the tests for your PR use the coverage as an handy
metric to guide you toward thoroughly tested code. **Do** try to cover all
important behaviour of your code but **don't** add a lot of mocks and/or
complexity to squeeze out just a little bit more coverage.

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

## Pull requests

### Signed commits required

- To get your changes accepted, please [sign your commits]. This practice is
enforced by many of the CI pipelines executed in the repository (pipelines
which use Canonical's [github-runner-operator] operated runners).
- If you have just discovered the requirement for signed commits after already
creating a feature branch with unsigned commits, you can issue
`git rebase --exec 'git commit --amend --no-edit -n -S' -i main` to sign them.
To translate this into English:
   - `git rebase --exec`: rebases commits
   - `--exec '...'`: exec command `'...'` after each commit, creating a new commit
   - `git commit --amend --no-edit`: amend a commit without changing its message
      - `-n`: bypass pre-commit and commit-msg hooks
      - `-S`: GPG sign commit
      - `-i`: let the user see and edit the list of commits to rebase
      - `main`: to all the commits until you reach main
- To make commit signing convenient, as per [this SO thread], do the following:

      git config --global user.signingkey <your-key-id>
      git config --global commit.gpgSign true
      git config --global tag.gpgSign true
      git config --global push.gpgSign if-asked

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

### Code review criteria & workflow

At all cases when a Checkbox maintainer picks up a PR for review, they are prepared to go back to the same PR if needed (if changes were requested).

As a general rule there is one reviewer per PR. Other reviewers may pop in to smooth up the process (where they feel confident they can _approve and merge_ changes after some were requested by another review). When more reviewers are needed an approval of, comments explaining that are made in the comment thread. Chiefly this is done to work around cases of low test coverage in cases when the changes affect something known to be of low quality (i.e. something significantly complex and hard to reason about, brittle, dated, known to have broken in the past).

The approving reviewer will merge the code if the review is accepted, and leave a comment if they have for some good reason decided not to merge it at approval time.

The reviewer is encouraged to use suggestions to communicate exact solutions and to make it easy to apply them. The reviewer _must_ do this when making trivial style related suggestions. The reviewer might also post code into the PR, or to a branch branched off from the feature branch, to communicate more complex suggestions. 

Checkbox maintainers will follow the following process to make the determination between "accept", "request changes" and "comment".

### Review will approve the pull request when...

1. They have read and understood the pull request description and changes being proposed.
2. The requirements laid out [in the PR template](.github/pull_request_template.md) are met. In particular:
  - the reviewer is convinced the changed code works as advertised
  - tests introduced cover the new functionality, as well as untouched code it may affect
  - testing reported by the author covers the new functionality, as well as untouched code it may affect 
  - if needed, reviewer has tested the changed solution locally

#### Reviewer will "request changes" to your PR when...

1. the pull request description is unclear, or it is clear that the changes do not meet the requirements [in the PR template](.github/pull_request_template.md).
1. doesn't do what is claimed.
2. introduces a new bug.
3. introduces a maintenance problem.
4. the solution is unnecessarily, significantly, too complex for the problem being solved
5. the introduced code/patch is very difficult to understand (the reviewer has doubts of understanding it right, or doubts that others would).

#### Review will "comment" if:

1. The reviewer's requests are subjective in nature, where the benefit is arguable (taste is a factor, e.g. arguable readability benefits).
2. The reviewer is proposing cleaner / simpler alternatives to some parts of the code being proposed that if un-addressed is not risky to address in follow-up.
3. The code was difficult to read, could be improved, but in the end you understood it.
4. You are unsure why something was done in particular way (you posted a question).
5. The problems the review points out are unrelated to what the PR is trying to do (the problem existed before).


## Documentation

[Checkbox documentation] lives in the `docs/` directory and is deployed on
[Read the Docs]. It is written using the [reStructuredText] format and built
using [Sphinx].

The documentation should follow the [style guide] in use for documentation
at Canonical. Please refer to it when proposing a change.

To install everything you need, go to the `docs/` directory and type:

    make install

This will create a virtual environment with all the tooling dedicated to
output and validate the documentation.

To get a live preview of the documentation, you can then run:

    make run

This will provide a link to a locally rendered version of the documentation
that will be updated every time a file is modified.

Finally, you can validate your changes with:

    make spelling  # to make sure there is no typos
    make linkcheck # to make sure there are no dead links
    make woke      # to check for non-inclusive language

***Note:*** Please make sure you wrap the text at 80 characters for easier
review of the source files.

Once all is good, you can submit your documentation change like any other
changes using a pull request.

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
[Checkbox documentation]: https://checkbox.readthedocs.io/
[Read the Docs]: https://www.readthedocs.com/
[reStructuredText]: https://docutils.sourceforge.io/rst.html
[Sphinx]: https://www.sphinx-doc.org/
[style guide]: https://docs.ubuntu.com/styleguide/en
[ShellCheck]: https://www.shellcheck.net/
[sign your commits]: https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits
[github-runner-operator]: https://github.com/canonical/github-runner-operator
[this SO thread]: https://stackoverflow.com/a/70484849/504931
