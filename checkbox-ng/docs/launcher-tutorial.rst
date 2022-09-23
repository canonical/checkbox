.. _launcher-tutorial:

Checkbox launchers tutorial
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Checkbox launchers are INI files that customize checkbox experience. The
customization includes:

* choosing what jobs will be run
* how to handle machine restart
* what type of UI to use
* how to handle the results

Each section in the launcher is optional, when not supplied, the default values
will be used.

This tutorial describes Launchers version 1.

External configuration files
============================

Launcher can specify external file(s) to load values from.

``[config]``

Beginning of the configuration section.

``config_filename``

Name of the configuration file to look for. Default value: ``checkbox.conf``

The directories that will be searched for the file are ``/etc/xdg/`` and
``~/.config/``.

Example::

    [config]
    config_filename = testing.conf

This will make checkbox look for ``/etc/xdg/testing.conf`` and
``~/config/testing.conf`` files.

The ``config_filename`` may be an absolute path, and may use environment
variables

Example::

    [config]
    config_filename = $MYCONFIGS/testing.conf

    [config]
    config_filename = /home/ubuntu/next-testing.conf

For more details about value resolution order see :doc:`configs</configs>`

Launcher meta-information
=========================

Launcher meta-information helps to provide consistent checkbox behaviour in the
future.

``[launcher]``

Beginning of the launcher meta-information section.

``app_id``

This fields helps to differentiate between checkbox front-ends. This way
sessions started with launcher with one ``app_id`` won't interfere with
sessions started with a different launcher (provided it has ``app_id`` set to
other value).  The app_id should be in a IQN form. Default value:
``com.canonical:checkbox-cli``

``app_version``

This field is purely informational.

``launcher_version``

Version of the launcher language syntax and semantics to use.

``api_flags``

API flags variable determines optional feature set.
List of API flags that this launcher requires. Items should be separated by
spaces or commas. The default value is an empty list.

``api_version``

API version determines the behaviour of the launcher. Each checkbox feature is
added at a specific API version. Default behaviours don't change silently;
explicit launcher change is required. Default value: ``0.99``

``session_title``

A title to be applied to the sessions created using this launcher. This can be
be used to identify a stored sessions and can be used in report generation.

``session_desc``

A string that can be applied to sessions created using this launcher. Useful
for storing some contextual information about the session.

``stock_reports``

Stock reports are shortcuts in creating common reports. Instead of having to
specify exporter, transport and a report section in a launcher, you can use any
number of the stock ones. In launchers version 1 there are 4 stock reports you
may use:

    * ``text`` - print results as text on standard output
    * ``submission_files`` - write ``html``, ``json`` and ``tar.xz``
      files to ``$XDG_DATA_HOME`` directory (or to ``~/.local/share/`` if
      ``$XDG_DATA_HOME`` is not defined.
    * ``certification`` - send results to certification site
    * ``certification-staging`` - send results to staging version of
      certification site

If you don't want to have any stock report automatically generated use
``none`` as the value.

This field is a list; use commas or spaces to separate stock reports. The
default value: ``text, certification, submission_files``.

When using ``certification`` stock report, the ``secure_id`` variable may be
overridden by the launcher.
To do this define ``secure_id`` in a ``transport:c3`` section (this is the
transport that's used by the ``certification`` stock reports).

Launcher section example:

::

    [launcher]
    app_id = com.foobar:system-testing
    launcher_version = 1
    stock_reports = text
    session_title = MegaCorp Thingy Alpha-1
    session_desc = Testing the alpha-1 release of MegaCorp Thingy including feature X

Launcher using all defaults with overridden secure_id:

::

    [transport:c3]
    secure_id = 001122334455667788

Launcher that disables all stock reports:

::

    [launcher]
    app_id = com.foobar:system-testing
    launcher_version = 1
    stock_reports = none

Test plan section
=================

This section provides control over which test plans are visible in the menus
and optionally forces the app to use particular one.

``[test plan]``

Beginning of the test plan section.

``unit``

An ID of a test plan that should be selected by default. By default nothing is
selected.

``filter``

Glob that test plan IDs have to match in order to be visible. Default value:
``*``

``forced``

If set to ``yes``, test plan selection screen will be skipped. Requires
``unit`` field to be set. Default value: ``no``.


Test selection section
======================
This section provides control over test selection.

``[test selection]``

Beginning of the test selection section

``forced``

If set to ``yes``, test selection screen will be skipped and all test specified
in the test plan will be selected. Default value: ``no``

``exclude``

List of regex patterns that job ids will be matched against. The matched jobs
will be excluded from running in both stages of the session: bootstrapping and
normal stage. Note that if you specify a pattern that matches a resource job
that is used to instantiate template units those units won't get generated. The
patterns should be separated with whitespace. Examples:

Exclude all jobs containing 'bluetooth' in their id:

::

    [test selection]
    exclude = .*bluetooth.*


Exclude all jobs containing ``bluetooth`` in their id, or having ids starting
with ``com.canonical.certification::dock/wireless``:

::

    [test selection]
    exclude = .*bluetooth.* com.canonical.certification::dock/wireless.*

Note: Exclude field set in launcher can be overridden in a config, following
Checkbox values resolution order. See :doc:`configs</configs>` for more info.

Note: To clear the exclude list use...

::

    exclude =

...in your 'last' config.


User Interface section
======================

This section controls which type of UI to use.

``[ui]``

Beginning of the user interface section

``type``

Type of UI to use. This has to be set to ``interactive``, ``silent``,
``converged``, or ``converged-silent``.

``interactive`` runs the standard Checkbox command line version that prompts
user in non-automated tests.

``silent`` skips the tests that would require human interaction. It's not
'silent' in the traditional command-line tool sense.

Default value: ``interactive``.

Note: the ``converged`` and ``converged-silent`` UI types will launch the QML
interface and requires checkbox-converged to be installed on your system.
Note: using ``silent`` or ``converged-silent`` UI types requires forcing
test selection and test plan selection.

``dont_suppress_output``

.. note::

    This field is deprecated, use 'output' to specify which jobs should have
    their output printed to the screen.

Setting this field to ``yes`` disables hiding of command output for jobs of
type ``resource`` and ``attachment``. Default value: ``no``.

``output``

This setting lets you hide output of commands run by checkbox. It can be set to
one of the following values:

- ``show`` - output of all jobs will be printed
- ``hide-resource-and-attachment`` - output of resource and attachment jobs
  will be hidden, output of other job types will be printed
- ``hide-automated`` - output of shell jobs as well as attachment and resource
  jobs will be hidden. Only interactive job command's output will be shown
- ``hide`` - same as ``hide-automated``. This value is deprecated, use
  ``hide-automated``

Default value: ``show``

.. note::

    Individual jobs can have their output hidden by specifying
    'suppress-output' in their definition.

``verbosity``

This setting makes checkbox report more information from checkbox internals.
Possible values are:

- ``normal`` - report only warnings and errors.
- ``verbose`` - report important events that take place during execution (E.g.
  adding units, starting jobs, changing the state of the session)

- ``debug`` - print out everything

Default value: ``normal``

.. note::

    You can also change this behavior when invoking Checkbox by using
    ``--verbose`` and ``--debug`` options respectively.

``auto_retry``

If set to ``yes``, failed jobs will automatically be retried at the end of
the testing session. In addition, the re-run screen (where user can select
failed and skipped jobs to re-run) will not be shown. Default value: ``no``.

``max_attempts``
Defines the maximum number of times a job should be run in auto-retry mode.
If the job passes, it won't be retried even if the maximum number of attempts
have not been reached. Default value: ``3``.

``delay_before_retry``
The number of seconds to wait before retrying the failed jobs at the end of
the testing session. This can be useful when the jobs rely on external
factors (e.g. a WiFi access point) and you want to wait before retrying the
same job. Default value: ``1``.

.. warning::

    When ``auto_retry`` is set to ``yes``, **every** failing job will be retried.
    This can be a problem, for instance, for jobs that take a really long time
    to run. To avoid this, you can use the ``auto-retry=no`` inline override
    in the test plan to explicitly mark each job you do not wish to see
    retried.

    For example::

        id: foo-bar-and-froz
        _name: Tests Foo, Bar and Froz
        include:
            foo
            bar     auto-retry=no
            froz

    In that case, even if job ``bar`` fails and auto-retry is activated, it
    will not be retried.

Restart section
===============

This section enables fine control over how checkbox is restarted.

``[restart]``

Beginning of the restart section

``strategy``

Override the restart strategy that should be used. Currently supported
strategies are ``XDG`` and ``Snappy``. By default the best strategy is
determined at runtime.

Environment section
===================

``[environment]``

Beginning of the environment section

Each variable present in the ``environment`` section will be present as
environment variable for all jobs run.

Example:

::

    [environment]
    TESTING_HOST = 192.168.0.100

.. _generating-reports:

Daemon-specific configuration
=============================

``[daemon]``

Beginning of the daemon-specific section.
Settings in this section only apply to sessions that are run by checkbox-slave
spawned as a daemon.

``normal_user``

Username to use when job doesn't specify which user to run as.

Checkbox-slave daemon is run by root so in order to run some jobs as an
unprivileged user this variable can be used.


Manifest section
================

``[manifest]``

Beginning of the manifest section.

Each variable present in the ``manifest`` section will be used as a preset value
for the system manifest, taking precedence over the disk cache.

Example:

::

    [manifest]
    com.canonical.certification::has_touchscreen = yes
    com.canonical.certification::has_usb_type_c = true
    com.canonical.certification::foo = 23


Generating reports
==================

Creation of reports is governed by three sections: ``report``, ``exporter``, and
``transport``. Each of those sections might be specified multiple times to
provide more than one report.

Exporter
--------

``[exporter:exporter_name]``

Beginning of an exporter declaration. Note that ``exporter_name`` should be
replaced with something meaningful, like ``html``.

``unit``

ID of an exporter to use. To get the list of available exporters on your system
run ``$ plainbox dev list exporter``.

``options``

A list of options that will be supplied to the exporter. Items should be separated by
spaces or commas.

Example:

::

    [exporter:html]
    unit = com.canonical.plainbox::html

Transport
---------

``[transport:transport_name]``
Beginning of a transport declaration. Note that ``transport_name`` should be
replaced with something meaningful, like ``standard_out``.

``type``

Type of a transport to use. Allowed values are: ``stream``, ``file``, and
``certification``.

Depending on the type of transport there might be additional fields.


+------------------------+---------------+----------------+----------------------+
| transport type         |  variables    | meaning        | example              |
+========================+===============+================+======================+
| ``stream``             | ``stream``    | which stream to| ``[transport:out]``  |
|                        |               | use ``stdout`` |                      |
|                        |               | or ``stderr``  | ``type = stream``    |
|                        |               |                |                      |
|                        |               |                | ``stream = stdout``  |
+------------------------+---------------+----------------+----------------------+
| ``file``               | ``path``      | where to save  | ``[transport:f1]``   |
|                        |               | the file       |                      |
|                        |               |                | ``type = file``      |
|                        |               |                |                      |
|                        |               |                | ``path = ~/report``  |
+------------------------+---------------+----------------+----------------------+
| ``submission-service`` | ``secure-id`` | secure-id to   | ``[transport:c3]``   |
|                        |               | use when       |                      |
|                        |               | uploading to   | ``secure_id = 01``\  |
|                        |               | certification  | ``23456789ABCD``     |
|                        |               | sites          |                      |
|                        |               |                | ``staging = yes``    |
|                        |               |                |                      |
|                        +---------------+----------------+                      |
|                        | ``staging``   | determines if  |                      |
|                        |               | staging site   |                      |
|                        |               | should be used |                      |
|                        |               | Default:       |                      |
|                        |               | ``no``         |                      |
|                        |               |                |                      |
|                        |               |                |                      |
|                        |               |                |                      |
+------------------------+---------------+----------------+----------------------+


Report
------

``[report:report_name]``

Beginning of a report declaration. Note that ``report_name`` should be
replaced with something meaningful, like ``to_screen``.

``exporter``

Name of the exporter to use

``transport``

Name of the transport to use

``forced``

If set to ``yes`` will make checkbox always produce the report (skipping the
prompt). Default value: ``no``.

Example of all three sections working to produce a report:

::

    [exporter:text]
    unit = com.canonical.plainbox::text

    [transport:out]
    type = stream
    stream = stdout

    [report:screen]
    exporter = text
    transport = out
    forced = yes


Launcher examples
=================

1) Fully automatic run of all tests from
'com.canonical.certification::smoke' test plan concluded by producing text
report to standard output.

::

    #!/usr/bin/env checkbox-cli

    [launcher]
    launcher_version = 1
    app_id = com.canonical.certification:smoke-test
    stock_reports = text

    [test plan]
    unit = com.canonical.certification::smoke
    forced = yes

    [test selection]
    forced = yes

    [ui]
    type = silent

    [transport:outfile]
    type = stream
    stream = stdout

    [exporter:text]
    unit = com.canonical.plainbox::text

    [report:screen]
    transport = outfile
    exporter = text

2) Interactive testing of FooBar project. Report should be uploaded to the
staging version of certification site and saved to /tmp/submission.tar.xz

::

    #!/usr/bin/env checkbox-cli

    [launcher]
    launcher_version = 1
    app_id = com.foobar:system-testing

    [providers]
    use = com.megacorp.foo::bar*

    [test plan]
    unit = com.megacorp.foo::bar-generic

    [ui]
    type = silent
    output = hide

    [transport:certification]
    type = certification
    secure-id = 00112233445566
    staging = yes

    [transport:local_file]
    type = file
    path = /tmp/submission.tar.xz

    [report:c3-staging]
    transport = certification
    exporter = tar

    [report:file]
    transport = local_file
    exporter = tar

3) A typical launcher to run a desktop SRU test plan automatically.
The launcher will automatically retry the failed test jobs. Besides,
this launcher includes another launcher ``launcher.conf`` as its
customized environment configuration.

The launcher

::

    #!/usr/bin/env checkbox-cli
    [launcher]
    launcher_version = 1

    [config]
    config_filename = $HOME/launcher.conf

    [test plan]
    unit = com.canonical.certification::sru
    forced = yes

    [test selection]
    forced = yes

    [ui]
    type = silent
    auto_retry = yes
    max_attempts = 3
    delay_before_retry = 15


The launcher configuration ``laucher.conf``

::

    #!/usr/bin/env checkbox-cli
    [launcher]
    launcher_version = 1
    stock_reports = text, submission_files, certification

    [transport:c3]
    secure_id = <your secure ID>

    [transport:local_file]
    type = file
    path = /home/ubuntu/c3-local-submission.tar.xz

    [exporter:example_tar]
    unit = com.canonical.plainbox::tar

    [report:file]
    transport = local_file
    exporter = tar
    forced = yes

    [environment]
    ROUTERS = multiple
    WPA_BG_SSID = foo-bar-bg-wpa
    WPA_BG_PSK = foo-bar
    WPA_N_SSID = foo-bar-n-wpa
    WPA_N_PSK = foobar
    WPA_AC_SSID = foo-bar-ac-wpa
    WPA_AC_PSK = foobar
    OPEN_BG_SSID = foo-bar-bg-open
    OPEN_N_SSID = foo-bar-n-open
    OPEN_AC_SSID = foo-bar-ac-open
    BTDEVADDR = ff:oo:oo:bb:aa:rr
    TRANSFER_SERVER = cdimage.ubuntu.com
