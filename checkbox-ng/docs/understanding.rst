Understanding Checkbox
======================

.. contents::

Checkbox by itself doesn't test anything. It uses unit definitions grouped in
providers to actually run or do something.

To better understand how Checkbox works let's concentrate on the relationship
between the following entities:

    - test command (program that is invoked as a test)
    - job unit
    - test plan
    - provider
    - launcher

Test Command
------------

Automated and some interactive tests use external commands to help determine the
outcome of the test. For instance the command::

    ping 8.8.8.8 -c 1

Will check whether the device can ping a public DNS.
The command returns 0 on success (ping came back), and 1 if the ping timed out.

Let's turn this simple command into a Checkbox test.


Job Unit
--------

The command from the above paragraph can now be used in a Job Unit::

    id: ping-public-dns
    _summary: Ping public DNS
    plugin: shell
    command: ping 8.8.8.8 -c 1

Notice how the command field is a straight copy-paste of the Test Command

**RELATIONSHIP: Test Command is a part of a Job Unit**

.. note::

    Some test are fully manual and don't run any commands.

See :ref:`units` for :ref:`more info on job units <job>`

Test Plan
---------

When Checkbox is run from commandline without any parameters, i.e.::

    $ checkbox-cli

It doesn't present all the tests available in the system. Checkbox asks the user
which Test Plan to use.

.. note::

    For how to directly run hand-picked jobs see: :ref:`run_subcmd`.

Test Plans are units for grouping related jobs together.
They also provide a mechanism for creating new jobs in runtime. The phase in
which this is done is known as bootstrapping. Good example for when the
bootstrapping is needed is testing multi-GPU system. No one knows upfront which
GPU(s) will be present in the system so bootstrapping phase will instantiate
appropriate job units from template units.

**RELATIONSHIP: Test Plan includes a job that can be run.**

**RELATIONSHIP: Test Plan can "generate" a job (through bootstrapping)
that can be run.**

You can read more about templates here: :ref:`templates`, and about test plans
here: :ref:`test-plan`.

Provider
--------

In order for Checkbox to *see* any jobs, test plans, and other units,
those units need to be written to a `.pxu` file located in a `unit`
subdirectory of a provider available in the system.

**RELATIONSHIP: Units are placed in a Provider**


See :ref:`tutorials` for a tutorial on how to create a provider from scratch.


Launcher
--------

Launchers can be used to make it easier to run Checkbox in a preset way.

Those can for instance preset:
    - which test plan to use
    - whether the session should be interactive or automated
    - which tests to exclude
    - how and where to submit the results

There is a full launcher tutorial here: :ref:`launcher-tutorial`.
