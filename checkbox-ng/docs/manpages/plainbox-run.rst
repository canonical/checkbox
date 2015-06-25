================
plainbox-run (1)
================

.. argparse::
    :ref: plainbox.impl.box.get_parser_for_sphinx
    :prog: plainbox
    :manpage:
    :path: run
    :nodefault:

    This command runs zero or more Plainbox jobs as a part of a single session
    and saves the test results. Plainbox will follow the following high-level
    algorithm during the execution of this command.

    1. Parse command line arguments and look if there's a session that can be
       resumed (see **RESUMING** below). If so, offer the user a choice to
       resume that session. If the resume operation fails move to the next
       qualifying session. Finally offer to create a new session.

    2. If the session is being resumed, replay the effects of the session
       execution from the on-disk state. This recreates generated jobs and
       re-introduces the same resources into the session state. In other words,
       no jobs that have run in the past are re-ran.

       If the resumed session was about to execute a job then offer to skip the
       job. This allows test operators to skip jobs that have caused the system
       to crash in the past (e.g. system suspend tests)

       If the session is not being resumed (a new session was created), set the
       `incomplete` flag.

    3. Use the job selection (see **SELECTING JOBS** below) to derive the run
       list. This step involves resolving job dependencies and reordering jobs
       if required.

    4. Follow the run list, executing each job in sequence if possible.  Jobs
       can be inhibited from execution by failed dependencies or failed
       (evaluating to non-True result) resource expressions.

       If at any time a new job is being re-introduced into the system (see
       **GENERATED JOBS** below) then the loop is aborted and control jumps
       back to step 3 to re-select jobs. Existing results are not discarded so
       jobs that already have some results are not executed again.

       Before and after executing any job the session state is saved to disk to
       allow resuming from a job that somehow crashes the system or crashes
       Plainbox itself.

    5. Remove the `incomplete` flag.

    6. Export the state of the session to the desired format (see **EXPORTING
       RESULTS**) and use the desired transport to send the results (see
       **TRANSPORTING RESULTS**).

    7. Set the `submitted` flag.

    SELECTING JOBS
    ==============

    Plainbox offers two mechanisms for selecting jobs. Both can be used at the
    same time, both can be used multiple times.

    Selecting jobs with patterns
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    The first mechanism is exposed through the ``--include-pattern PATTERN``
    command-line option. It instructs Plainbox to `select` any job whose
    fully-qualified identifier matches the regular expression ``PATTERN``.

    Jobs selected this way will be, if possible, ordered according to the order
    of command line arguments. For example, having the following command line
    would run the job `foo` before running the job `bar`:

        plainbox run -i '.*::foo' -i '.*::bar'

    Selecting jobs with whitelists
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    The second mechanism is the ``--whitelist WHITELIST`` command-line option.
    WhiteLists (or test plans, which is somewhat easier to relate to).
    Whitelists are simple text files composed of a list of regular expressions,
    identical to those that may be passed with the ``-i`` option.

    Unlike the ``-i`` option though, there are two kinds of whitelists.
    Standalone whitelists are not associated with any Plainbox Provider.  Such
    whitelists can be distributed entirely separately from any other component
    and thus have no association with any namespace.

    Therefore, be fully qualified, each pattern must include both the namespace
    and the partial identifier components. For example, this is a valid, fully
    quallified whitelist::

        2013.com.canonical.plainbox::stub/.*

    It will unambiguously select some of the jobs from the special, internal
    StubBox provider that is built into Plainbox. It can be saved under any
    filename and stored in any directory and it will always select the same set
    of jobs.

    In contrast, whitelists that are associated with a particular provider, by
    being stored in the per-provider ``whitelists/`` directory, carry an
    implicit namespace. Such whitelists are typically written without
    mentioning the namespace component.

    For example, the same "stub/.*" pattern can be abbreviated to::

        stub/.*

    Typically this syntax is used in all whitelists specific to a particular
    provider unless the provider maintainer explicitly wants to include a job
    from another namespace (for example, one of the well-known Checkbox job
    definitions).

    GENERATED JOBS
    ==============

    Plainbox offers a way to generate jobs at runtime. There are two
    motivations for this feature.

    Instantiating Tests for Multiple Devices
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    The classic example is to probe the hardware (for example, to enumerate all
    storage devices) and then duplicate each of the store specific tests so
    that all devices are tested separately.

    At this time jobs can be generated only from jobs using the plugin type
    `local`. Jobs of this kind are expected to print fully conforming job
    definitions on stdout. Generated jobs cause a few complexities and one
    limitation that is currently enforced is that generated jobs cannot
    generate additional jobs if any of the affected jobs need to run as another
    user.

    Another limitation is that jobs cannot override existing definitions.

    Creating Parent-Child Association
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    A relatively niche and legacy feature of generated jobs is to print a
    verbatim copy of existing job definitions from a ``local`` job definition
    named afer a generic testing theme or category. For example the Checkbox
    job definition ``__wireless__`` prints, with the help of ``cat`` (1), all
    of the job definitions defined in the file ``wireless.txt``.

    This behavior is special-cased not to cause redefinition errors. Instead,
    existing definitions gain the ``via`` attribute that links them to the
    generator job. This feature is used by derivative application such as
    Checkbox. Plainbox is not using it at this time.

    RESUMING
    ========

    Plainbox offers a session resume functionality whereas a session that was
    interrupted (either purposefully or due to a malfunction) can be resumed
    and effectively continued where it was left off.

    When resuming a session you may be given an option to either re-run, pass,
    fail or skip the test job that was being executed before the session was
    interrupted. This is intended to handle both normal situations, such as a
    "system reboot test" where it is perfectly fine to "pass" the test without
    re-running the command. In addition it can be used to handle anomalous
    cases where the machine misbehaves and re-running the same test would cause
    the problem to occur again indefinitely.

    Limitations
    ^^^^^^^^^^^

    This functionality does not allow to interrupt and resume a test job that
    is already being executed. Such job will be restarted from scratch.

    Plainbox tries to ensure that a single session is consistent and the
    assumptions that held at the start of the session are maintained at the
    end. To that end, Plainbox will try to ensure that job definitions have not
    changed between two separate invocations that worked with a single session.
    If such a situation is detected the session will not be resumed.

    EXPORTING RESULTS
    =================

    Plainbox offers a way to export the internal state of the session into a
    more useful format for further processing.

    Selecting Exporters
    ^^^^^^^^^^^^^^^^^^^

    The exporter can be selected using the ``--output-format FORMAT``
    command-line option. A list of available exporters (which may include 3rd
    party exporters) can be obtained by passing the ``--output-format ?``
    option.

    Some formats are more useful than others in that they are capable of
    transferring more of the internal state. Depending on your application you
    may wish to choose the most generic format (json) and process it further
    with additional tools, choose the most basic format (text) just to get a
    simple summary of the results or lastly choose one of the two specialized
    formats (xml and html) that are specific to the Checkbox workflow.

    Out of the box the following exporters are supported:

    html
    ----

    This exporter creates a static HTML page with human-readable test report.
    It is useful for communicating with other humans and since it is entirely
    standalone and off-line it can be sent by email or archived.

    json
    ----

    This exporter creates a JSON document with the internal representation
    of the session state. It is the most versatile exporter and it is useful
    and easy for further processing. It is not particularly human-readable
    but can be quite useful for high-level debugging without having to use
    pdb and know the internals of Plainbox.

    rfc822
    ------

    This exporter creates quasi-RFC822 documents. It is rather limited and not
    used much. Still, it can be useful in some circumstances.

    text
    ----

    This is the default exporter. It simply prints a human-readable
    representation of test results without much detail. It discards nearly all
    of the internal state though.

    xlsx
    ----

    This exporter creates a standalone .xlsx (XML format for Microsoft Excel)
    file that contains a human-readable test report. It is quit similar to the
    HTML report but it is easier to edit. It is useful for communicating with
    other humans and since it is entirely standalone and off-line it can be
    sent by email or archived.

    It depends on python3-xlsxwriter package

    hexr
    ----

    This exporter creates a rather confusingly named XML document only
    applicable for internal Canonical Hardware Certification Team workflow.

    It is not a generic XML representation of test results and instead it
    carries quite a few legacy constructs that are only retained for
    compatibility with other internal tools. If you want generic processing
    look for JSON instead.

    Selecting Exporter Options
    ^^^^^^^^^^^^^^^^^^^^^^^^^^

    Certain exporters offer a set of options that can further customize the
    exported data. A full list of options available for each exporter can be
    obtained by passing the ``--output-options ?`` command-line option.

    Options may be specified as a comma-separated list. Some options act as
    simple flags, other options can take an argument with the ``option=value``
    syntax.

    Known exporter options are documented below:

    json
    ----

    with-io-log:
        Exported data will include the input/output log associated with each
        job result. The data is included in its native three-tuple form unless
        one of the `squash-io-log` or `flatten-io-log` options are used as
        well.

        IO logs are representations of the data produced by the process created
        from the shell command associated with some jobs.

    squash-io-log:
        When used together with `with-io-log` option it causes Plainbox to
        discard the stream name and time-stamp and just include a list of
        base64-encoded binary strings. This option is more useful for
        reconstructing simple "log files"

    flatten-io-log:
        When used together with `with-io-log` option it causes Plainbox to
        concatenate all of the separate base64-encoded records into one large
        base64-encoded binary string representing the whole communication that
        took place.

    with-run-list:
        Exported data will include the run list (sequence of jobs computed from
        the desired job list).

    with-job-list:
        Exported data will include the full list of jobs known to the system

    with-resource-map:
        Exported data will include the full resource map. Resources are records
        of key-value sets that are associated with each job result for jobs
        that have plugin type `resource`. They are expected to be printed to
        `stdout` by such `resource jobs` and are parsed and stored by Plainbox.

    with-job-defs:
        Exported data will include some of the properties of each job
        definition. Currently this set includes the following fields: `plugin`,
        `requires`, `depends`, `command` and `description`.

    with-attachments:
        Exported data will include attachments. Attachments are created from
        `stdout` stream of each job having plugin type `attachment`. The actual
        attachments are base64-encoded.

    with-comments:
        Exported data will include comments added by the test operator to each
        job result that has them.

    with-job-via:
        Exported data will include the ``via`` attribute alongside each job
        result. The via attribute contains the checksum of the job definition
        that generated a particular job definition. This is useful for tracking
        jobs generated by jobs with the plugin type `local`.

    with-job-hash:
        Exported data will include the ``hash`` attribute alongside each job
        result. The hash attribute is the checksum of the job definition's
        data. It can be useful alongside with `with-job-via`.

    machine-json:
        The generated JSON document will be minimal (devoid of any optional
        whitespace). This option is best to be used if the result is not
        intended to be read by humans as it saves some space.

    rfc822
    ------

    All of the options have the same meaning as for the `json` exporter:
    `with-io-log`, `squash-io-log`, `flatten-io-log`, `with-run-list`,
    `with-job-list`, `with-resource-map`, `with-job-defs`, `with-attachments`,
    `with-comments`, `with-job-via`, `with-job-hash`.  The only exception is
    the `machine-json` option which doesn't exist for this exporter.

    text
    ----

    Same as with rfc822.

    xlsx
    ----

    with-sys-info:
        Exported spreadsheet will include a worksheet detailing the hardware
        devices based on lspci, lsusb, udev, etc.

    with-summary:
        Exported spreadsheet will include test figures. This includes the
        percentage of tests that have passed, have failed, have been skipped
        and the total count.

    with-job-description:
        Exported spreadsheet will include job descriptions on a separate sheet

    with-text-attachments:
        Exported spreadsheet will include text attachments on a separate sheet

    xml
    ---

    client-name:
        This option allows clients to override the name of the application
        generating the XML document. By default that name is `plainbox`.  To
        use this option pass ``--output-options client-name=other-name``
        command-line option.

    TRANSPORTING RESULTS
    ====================

    Exported results can be either saved to a file (this is the most basic,
    default transport) or can be handed to one of the transport systems for
    further processing. The idea is that specialized users can provide their
    own transport systems (often coupled with a specific exporter) to move the
    test results from the system-under-test to a central testing result
    repository.

    Transport can be selected with the ``--transport`` option. Again, as with
    exporters, a list of known transports can be obtained by passing the
    ``--transport ?`` option. Transports need a destination URL which can be
    specified with the ``--transport-where=`` option. The syntax of the URL
    varies by transport type.

    Plainbox comes equipped with the following transports:

    launchpad
    ^^^^^^^^^

    This transport can send the results exported using ``xml`` exporter to the
    Launchpad Hardware Database. This is a little-known feature offered by the
    https://launchpad.net/ website.

    certification
    ^^^^^^^^^^^^^

    This transport can send the results exported using the ``xml`` exporter to
    the Canonical Certification Website (https://certification.canonical.com).

    This transport is of little use to anyone but the Canonical Hardware
    Certification Team that also maintains Plainbox and Checkbox but it is
    mentioned here for completeness.

See Also
========

:doc:`plainbox-dev-analyze`
