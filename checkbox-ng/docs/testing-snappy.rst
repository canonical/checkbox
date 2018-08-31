.. _testing-snappy:

Running Checkbox on Ubuntu Core
===============================


Introduction
------------

Checkbox is a hardware testing tool developed by Canonical for certifying
hardware with Ubuntu. Checkbox is free software and is available at
https://launchpad.net/checkbox-project.

To support the release of devices running snappy Ubuntu Core, Canonical has
produced versions of Checkbox tailored specifically for these systems.

This document aims to provide the reader with enough information to install and
run Checkbox on an Ubuntu Core system, and how to view/interpret/submit test
results.


Installation
------------

Installing Ubuntu Core on KVM
`````````````````````````````

Follow the `Ubuntu tutorial <https://www.ubuntu.com/download/iot/kvm>`_
to install Ubuntu Core on KVM.

Installing Checkbox Snap
````````````````````````

Now you are ready to install the Checkbox snap,
install it straight from the store::

    $ snap install checkbox-snappy --devmode


Running Checkbox
----------------

Launch Checkbox using::

    $ checkbox-snappy.test-runner

.. image:: _images/checkbox-snappy-1-test-plan.png

Checkbox keeps track of previous test runs, so if a session is not completed,
you’ll be asked to resume your previous run or create a new session:

.. image:: _images/checkbox-snappy-2-resume-session.png

The first selection screen will ask you to select a test plan to run:

.. image:: _images/checkbox-snappy-1-test-plan.png

Move the selection with the arrow keys, select with ``Space`` and confirm your
choice by pressing ``Enter``.  The next screen will allow you to fine tune the
tests you want to run:

.. image:: _images/checkbox-snappy-3-select-jobs.png

Tests are grouped by categories. Expand/collapse with ``Enter``, select/unselect
with ``Space`` (also works on categories). Press ``S`` to select all and ``D`` to
deselect all the tests. Press ``H`` to display a help screen with more keyboard
shortcuts.

Start the tests by pressing ``T``.

Checkbox is a test runner able to process fully automated tests/commands and
tests requiring user interaction (whether to setup or plug something to the
device, e.g. USB insertion or to confirm that the device acts as expected, e.g.
a led blinks).

Please refer to the Checkbox documentation to learn more about the supported
types of tests.

A fully automated test will stream stdout/stderr to your terminal allowing you
to immediately look at the I/O logs (if the session is run interactively).
Attachments jobs are treated differently as they could generate lots of I/O.
Therefore their outputs are hidden by default.

Interactive jobs will pause the test runner and detail the steps to complete
the test:

.. image:: _images/checkbox-snappy-4-user-interact-job.png


Getting Results
---------------

When the test selection has been run, the first displayed screen will allow you
to re-run failed jobs:

.. image:: _images/checkbox-snappy-5-rerun-jobs.png

Commands to select the tests to rerun are the same used to select tests in the
first selection screen. Here you can re-run your selection with ``R`` or finish
the session by pressing ``F``.

Checkbox will then print the the test results in the terminal and save them in
different formats locally on the device (and print their respective filenames):

.. image:: _images/checkbox-snappy-6-test-results.png

The resulting reports can be pulled from the system via ``scp`` for instance.
