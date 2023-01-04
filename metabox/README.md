# Introduction

[Checkbox] is used on a wide variety of devices (laptops, servers, IoT), with a variety of releases (18.04, 20.04, etc.), in a few different ways (run locally, using Checkbox remote). Over the years, manually testing Checkbox before each stable release has become more and more difficult.

Comes Metabox.

Metabox is a program that uses [Linux containers (LXC)] to deploy and test Checkbox in many different configurations, using many different scenarios.

Users define what configuration(s) they want, and Metabox handles the rest!

# How does it work?

Metabox comes with **scenarios** to test different parts of Checkbox. A scenario is a Python package that defines what to run, and what is expected to happen. For instance, the [`desktop_env` scenario] prepares a launcher with a simple test plan containing desktop jobs, executes it and makes sure the jobs pass and their output contain some expected information.

Users define **configurations** to execute these scenarios. A configuration is a Python module that contains what version(s) of Checkbox must be tested, and on what Ubuntu release(s). Some configurations can be found in the [`configs` directory], but users can write their own.

# Installation

Metabox requires LXD. Check the [LXD documentation to install and initialize it].

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

Let's say I want to test:

- the [`basic` scenario] (which focuses on Checkbox local)
- using the latest Debian version of Checkbox available in the Daily Builds PPA
- on bionic (18.04) and focal (20.04)
- for Checkbox local only (not Checkbox remote)

I can create the following `local-daily-builds-config.py` file:

```python
configuration = {
    'local': {
        'origin': 'ppa',
        'uri': 'ppa:checkbox-dev/ppa',
        'releases': ['bionic', 'focal'],
    },
}
```

Then call Metabox with it:

```
$ metabox local-daily-builds-config.py --do-not-dispose --tag basic
```

- `--tag basic` will ensure only scenarios that contains the term `basic` will be run.
- `--do-not-dispose` prevents Metabox from deleting the Linux containers it created. This will save you tons of time, since Metabox will only download the required image and setup the container once, create a snapshot, then stop the container once the testing is done. The next time you run the command, Metabox will reopen the existing container and rollback to a clean state in it before starting the new tests.

[Checkbox]: https://checkbox.readthedocs.io/
[Linux containers (LXC)]: https://linuxcontainers.org/
[`desktop_env` scenario]: ./metabox/scenarios/desktop_env/
[`basic` scenario]: ./metabox/scenarios/basic/
[`configs` directory]: ./configs/
[LXD documentation to install and initialize it]: https://linuxcontainers.org/lxd/getting-started-cli/
