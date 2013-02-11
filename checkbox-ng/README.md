plainbox
========

plainbox is a plain replacement for checkbox

[![Build Status](https://travis-ci.org/zyga/plainbox.png)](https://travis-ci.org/zyga/checkbox)


Hacking
=======

To start hacking use virtualenv with python3. Three steps:


1. First install a couple of packages:

    $ sudo apt-get install python-virtualenv python3-dev

2. Then set up the virtualenv. A convenience script is provided to do this for
   you:

    $ ./mk-venv.sh /path/to/venv

This will create a virtualenv under /tmp/venv and show the command to activate
it.

You can also set this up manually:

    $ virtualenv -p python3 /path/to/venv

If you do the manual setup and you're on  Ubuntu, you'll need to update the
version of distribute that is installed inside the virtualenv to install
coverage. If you used the convenience script, it takes care of this part for
you.

    (venv) $ easy_install -U distribute
    (venv) $ easy_install -U coverage

3. Once your virtualenv is set up, you need to activate it:

    $ . /path/to/venv/bin/activate


Then 'develop' the package, this will setup proper path imports and create stub
executables for you. All imports will now use your directory (no need to set
PYTHONPATH to anything)

    (venv) $ python3 setup.py develop

You will be now able to run plainbox:

    (venv) $ plainbox --help

Testing
=======

When hacking, run tests with code coverage (peek at .coveragerc):

    (venv) $ coverage run setup.py test

You can also use the standard 'discover' command from python3 unittest module:

    (venv) $ coverage run -m unittest discover

...then look at test report coverage in the console:

    (venv) $ coverage report

...or in your browser:

    (venv) $ coverage html
    (venv) $ xdg-open htmlcov/index.html

Using the checkbox submodule
============================

This git tree uses the submodule system to put the entire checkbox source code
repository in the checkbox directory. To use it, after you get the plainbox
tree run the following commands:

    $ git submodule init
    $ git submodule update

You only need to run init once, and update each time the chcekbox submodule is
updated to point to new commit in the checkbox tree. If you use this all of
plainbox tests and actual code will run using the embedded copy of checkbox. If
you don't do this you need to install checkbox globally using a system package.

VirtualEnv and checkbox Jobs
============================

When using checkbox inside virtualenv some jobs will fail as they need access
to system python libraries (most notably for dbus). checkbox jobs don't rewrite
their scripts shebang lines so when installed from the system package it will
fail inside a typical virtualenv. This will be addressed in the next release.

To work around it, temporarily, you can install plainbox without virtualbox and
use it as is. This will work correctly (use the package from
ppa:checkbox-dev/ppa if possible)

Known Issues
============

There are a few issues that we are currently aware of:

1) Expressions are not evaluated the same way as they were in checkbox. This
affects only a few jobs and will be corrected in the next release. Most likely
we will adapt jobs to follow plainbox logic and leave the checkbox interpreter
as is as plainbox is less surprising and actually fixes one important bug where
an expression like:

    package.name == "foo" and package.version == "1.0"

When executed inside checkbox it would match (evaluate as true) when the
package "foo" existed and any _other_ package with version 1.0 existed, thus
making the test worthless. In plainbox this test behaves as expected but it is
non the less not doing what checkbox did so it causes some problems.

2) Many job types are still not supported. The only supported jobs are: shell, resource,
local and manual

3) Jobs that use the environ and user keys are not supported. Those keys are ignored
