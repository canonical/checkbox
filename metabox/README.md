# Introduction

[Checkbox] is used on a wide variety of devices (laptops, servers, IoT), with a
variety of releases (18.04, 20.04, etc.), in a few different ways (run locally,
using Checkbox remote). Over the years, manually testing Checkbox before each
stable release has become more and more difficult.

Enter Metabox.

Metabox is a program that uses [Linux containers (LXC)] to deploy and test
Checkbox in many different configurations, using many different scenarios.

Users define what configuration(s) they want, and Metabox handles the rest!

# How does it work?

Metabox comes with **scenarios** to test different parts of Checkbox. A
scenario is a Python module that defines what to run, and what is expected to
happen. For instance, the [`desktop_env` scenario] prepares a launcher with a
simple test plan containing desktop jobs, executes it and makes sure the jobs
pass and their output contain some expected information.

Users define **configurations** to execute these scenarios. A configuration is
a Python module that contains what version(s) of Checkbox must be tested, and
on what Ubuntu release(s). Some configurations can be found in the [`configs`
directory], but users can write their own.

# Installation

Metabox requires LXD. Check the [LXD documentation to install and initialize
it].

Create a Python virtual environment and install Metabox in it:

```shell
$ cd metabox/
$ python3 -m venv metabox
$ source metabox/bin/activate
(metabox) $ pip install -e .
```

# Usage

```
usage: metabox [-h] [--tag TAGS] [--exclude-tag EXCLUDE_TAGS] [--log {TRACE,DEBUG,INFO,SUCCESS,WARNING,ERROR,CRITICAL}] [--do-not-dispose] [--hold-on-fail] [--debug-machine-setup] CONFIG

positional arguments:
  CONFIG                Metabox configuration file

optional arguments:
  -h, --help            show this help message and exit
  --tag TAGS            Run only scenario with the specified tag. Can be used multiple times.
  --exclude-tag EXCLUDE_TAGS
                        Do not run scenario with the specified tag. Can be used multiple times.
  --log {TRACE,DEBUG,INFO,SUCCESS,WARNING,ERROR,CRITICAL}
                        Set the logging level
  --do-not-dispose      Do not delete LXD containers after the run
  --hold-on-fail        Pause testing when a scenario fails
  --debug-machine-setup
                        Turn on verbosity during machine setup. Only works with --log TRACE
```

## Examples

### Testing Checkbox from a PPA

Let's say I want to test:

- the [`basic` scenario] (which focuses on Checkbox local)
- using the latest Debian version of Checkbox available in the Edge PPA
- on bionic (18.04) and focal (20.04)
- for Checkbox local only (not Checkbox remote)

I can create the following `local-daily-builds-config.py` file:

```python
configuration = {
    'local': {
        'origin': 'ppa',
        'uri': 'ppa:checkbox-dev/edge',
        'releases': ['bionic', 'focal'],
    },
}
```

Then call Metabox with it:

```
$ metabox local-daily-builds-config.py --do-not-dispose --tag basic
```

- `--tag basic` will ensure only scenarios that contains the term `basic` will
be run.
- `--do-not-dispose` prevents Metabox from deleting the Linux containers it
created. This will save you tons of time, since Metabox will only download the
required image and setup the container once, create a snapshot, then stop the
container once the testing is done. The next time you run the command, Metabox
will reopen the existing container and rollback to a clean state in it before
starting the new tests.

### Testing Checkbox from a local repository

It is possible to test Checkbox directly from a local Git repository using the
`source` origin. To test all the available Metabox scenarios on Jammy using
a local copy of Checkbox, create the following `source-local-config.py` file:

```python
configuration = {
    'local': {
        'origin': 'source',
        # Path to the Checkbox source code repository.
        # Can be omitted, see below.
        'uri': '~/checkbox',
        'releases': ['jammy'],
    },
}
```

Then call Metabox using it:

```
$ metabox source-local-config.py
```

**Note:** if `origin` is set to `source`, `uri` is not mandatory. If it is not
set, it will point to the parent directory of the Metabox package. For
instance, if Metabox was [installed] from `/home/user/code/checkbox/metabox/`,
`uri` will be set to `/home/user/code/checkbox/`.

### Testing Checkbox remote

You can test your local modifications to Checkbox Remote with the following
configuration:

```python
configuration = {
    'remote': {
        'origin': 'source',
        'uri': '~/checkbox',
        'releases': ['jammy', 'focal', 'bionic'],
    },
    'agent': {
        'origin': 'source',
        'uri': '~/checkbox',
        'releases': ['jammy', 'focal', 'bionic'],
    },
}
```

**Note:** Metabox is always going to check **all possible combinations** of
`releases`, that means that this example will execute 9 test runs.

### Testing Checkbox Snaps

Metabox is able to test both locally built and store snaps.

To test a store snap you can use the following config:

```python
# The syntax and its meaning is similar to above, the following will run
# all local and remote tests for the focal snap
configuration = {
    "local": {
        "origin": "classic-snap",
        # Use the store core snap on the "edge" channel
        "checkbox_core_snap": {"risk": "edge"},
        # Use the store frontend snap on the "edge" channel
        "checkbox_snap": {"risk": "edge"},
        "releases": ["focal"],
    },
    "remote": {
        "origin": "classic-snap",
        "checkbox_core_snap": {"risk": "edge"},
        "checkbox_snap": {"risk": "edge"},
        "releases": ["focal"],
    },
    "service": {
        "origin": "classic-snap",
        "checkbox_core_snap": {"risk": "edge"},
        "checkbox_snap": {"risk": "edge"},
        "releases": ["focal"],
    },
}
```

To test a locally built snap you can use the following config:
```python
configuration = {
    "local": {
        "origin": "classic-snap",
        "checkbox_core_snap": {"uri": "~/checkbox22.snap"},
        # Note: you can mix and match, for example this uses a locally built
        #       snap for runtime but a store version of frontend
        "checkbox_snap": {"risk": "edge"},
        "releases": ["jammy"],
    },
}
```

[Checkbox]: https://checkbox.readthedocs.io/
[Linux containers (LXC)]: https://linuxcontainers.org/
[`desktop_env` scenario]: ./metabox/scenarios/desktop_env/
[`basic` scenario]: ./metabox/scenarios/basic/
[`configs` directory]: ./configs/
[LXD documentation to install and initialize it]: https://linuxcontainers.org/lxd/getting-started-cli/
[installed]: #installation
