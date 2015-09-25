======================
plainbox-job-units (7)
======================

Synopsis
========

This page documents the syntax of the plainbox job units

Description
===========

A job unit is a smallest unit of testing that can be performed by either
Checkbox or Plainbox. All jobs have an unique name. There are many types of
jobs, some are fully automated others are fully manual. Some jobs are only an
implementation detail and a part of the internal architecture of Checkbox.

File format and location
------------------------

Jobs are expressed as sections in text files that conform somewhat to the
``rfc822`` specification format. Our variant of the format is described in
rfc822. Each record defines a single job.

Job Fields
----------

Following fields may be used by the job unit:

``id``:
    (mandatory) - A name for the job. Should be unique, an error will
    be generated if there are duplicates. Should contain characters in
    [a-z0-9/-].
    This field used to be called ``name``. That name is now deprecated. For
    backwards compatibility it is still recognized and used if ``id`` is
    missing.

``summary``:
    (mandatory) - A human readable name for the job. This value is available
    for translation into other languages. It is used when listing jobs. It must
    be one line long, ideally it should be short (50-70 characters max).

``plugin``:
    (mandatory) - For historical reasons it's called "plugin" but it's
    better thought of as describing the "type" of job. The allowed types
    are:

     :manual: jobs that require the user to perform an action and then
          decide on the test's outcome.
     :shell: jobs that run without user intervention and
         automatically set the test's outcome.
     :user-interact: jobs that require the user to perform an
         interaction, after which the outcome is automatically set.
     :user-interact-verify: jobs that require the user to perform an
        interaction, run a command after which the user is asked to decide on the
        test's outcome. This is essentially a manual job with a command.
     :attachment: jobs whose command output will be attached to the
         test report or submission.
     :local: a job whose command output needs to be in Checkbox job
         format. Jobs output by a local job will be added to the set of
         available jobs to be run.
     :resource: A job whose command output results in a set of rfc822
          records, containing key/value pairs, and that can be used in other
          jobs' ``requires`` expressions.
     :qml: jobs that run a custom QML payload within a test shell (QML
        application or a generic, minimalistic QML test shell) using test API
        described in CEP-5

.. warning::
     The following plugin names are deprecated:

     :user-verify: jobs that automatically perform an action or test
         and then request the user to decide on the test's outcome.  This was
         deprecated because the user had no chance to read instructions prior
         to the test. Use user-interact-verify instead; that will present
         instructions, ask the user to click a button before running the
         command, and finally prompt for outcome assessment.

``requires``:
    (optional). If specified, the job will only run if the conditions
    expressed in this field are met.

    Conditions are of the form ``<resource>.<key> <comparison-operator>
    'value' (and|or) ...`` . Comparison operators can be ==, != and ``in``.
    Values to compare to can be scalars or (in the case of the ``in``
    operator) arrays or tuples. The ``not in`` operator is explicitly
    unsupported.

    Requirements can be logically chained with ``or`` and
    ``and`` operators. They can also be placed in multiple lines,
    respecting the rfc822 multi-line syntax, in which case all
    requirements must be met for the job to run ( ``and`` ed).

    The Plainbox resource program evaluator is extensively documented,
    to see a detailed description including rationale and implementation of
    Checkbox "legacy" compatibility, see
    `http://plainbox.readthedocs.org/en/latest/dev/resources.html#resources-in-plainbox`

``depends``:
    (optional). If specified, the job will only run if all the listed
    jobs have run and passed. Multiple job names, separated by spaces,
    can be specified.

``after``:
    (optional). If specified, the job will only run if all the listed jobs have
    run (regardless of the outcome). Multiple job names, separated by spaces,
    can be specified.

    This feature is available since plainbox 0.24.

``command``:
    (optional). A command can be provided, to be executed under specific
    circumstances. For ``manual``, ``user-interact`` and ``user-verify``
    jobs, the command will be executed when the user presses a "test"
    button present in the user interface. For ``shell`` jobs, the
    command will be executed unconditionally as soon as the job is
    started. In both cases the exit code from the command (0 for
    success, !0 for failure) will be used to set the test's outcome. For
    ``manual``, ``user-interact`` and ``user-verify`` jobs, the user can
    override the command's outcome.  The command will be run using the
    default system shell. If a specific shell is needed it should be
    instantiated in the command. A multi-line command or shell script
    can be used with the usual multi-line syntax.

    Note that a ``shell`` job without a command will do nothing.

``description``:
    (mandatory). Provides a textual description for the job. This is
    mostly to aid people reading job descriptions in figuring out what a
    job does.

    The description field, however, is used specially in ``manual``,
    ``user-interact`` and ``user-verify`` jobs. For these jobs, the
    description will be shown in the user interface, and in these cases
    it's expected to contain instructions for the user to follow, as
    well as criteria for him to decide whether the job passes or fails.
    For these types of jobs, the description needs to contain a few
    sub-fields, in order:

    :PURPOSE: This indicates the purpose or intent of the test.
    :STEPS: A numbered list of steps for the user to follow.
    :INFO:
        (optional). Additional information about the test. This is
        commonly used to present command output for the user to validate.
        For this purpose, the ``$output`` substitution variable can be used
        (actually, it can be used anywhere in the description). If present,
        it will be replaced by the standard output generated from running
        the job's command (commonly when the user presses the "Test"
        button).
    :VERIFICATION:
        A question for the user to answer, deciding whether the test
        passes or fails. The question should be phrased in such a way
        that an answer of **Yes** means the test passed, and an answer of
        **No** means it failed.

.. warning::
    since version 0.17 fields: purpose, steps and verification should be used
    instead of description.

``Example:``
   `old-way`:
    _description:
     PURPOSE:
         This test will check that internal speakers work correctly
     STEPS:
         1. Make sure that no external speakers or headphones are connected
            When testing a desktop, you can skip this test if there is no
            internal speaker, we will test the external output later
         2. Click the Test button to play a brief tone on your audio device
     VERIFICATION:
         Did you hear a tone?
   `new-way`:
    _purpose:
         This test will check that internal speakers work correctly
    _steps:
         1. Make sure that no external speakers or headphones are connected
            When testing a desktop, you can skip this test if there is no
            internal speaker, we will test the external output later
         2. Click the Test button to play a brief tone on your audio device
    _verification:
        Did you hear a tone?

    Note that if client code references the description field, plainbox will
    combine purpose, steps and verification fields into one and use the result

``purpose``:
    (optional). Purpose field is used in tests requiring human interaction as
    an information about what a given test is supposed to do. User interfaces
    should display content of this field prior to test execution. This field
    may be omitted if the summary field is supplied.
    Note that this field is applicable only for human interaction jobs.

``steps``:
    (optional). Steps field depicts actions that user should perform as a part
    of job execution. User interfaces should display the content of this field
    upon starting the test.
    Note that this field is applicable only for jobs requiring the user to
    perform some actions.

``verification``:
    (optional). Verification field is used to inform the user how they can
    resolve a given job outcome.
    Note that this field is applicable only for jobs the result of which is
    determined by the user.

``user``:
    (optional). If specified, the job will be run as the user specified
    here. This is most commonly used to run jobs as the superuser
    (root).

``environ``:
    (optional). If specified, the listed environment variables
    (separated by spaces) will be taken from the invoking environment
    (i.e. the one Checkbox is run under) and set to that value on the
    job execution environment (i.e.  the one the job will run under).
    Note that only the *variable names* should be listed, not the
    *values*, which will be taken from the existing environment. This
    only makes sense for jobs that also have the ``user`` attribute.
    This key provides a mechanism to account for security policies in
    ``sudo`` and ``pkexec``, which provide a sanitized execution
    environment, with the downside that useful configuration specified
    in environment variables may be lost in the process.

``estimated_duration``:
    (optional) This field contains metadata about how long the job is
    expected to run for, as a positive float value indicating
    the estimated job duration in seconds.

    Since plainbox version 0.24 this field can be expressed in two formats. The
    old format, a floating point number of seconds is somewhat difficult to
    read for larger values. To avoid mistakes test designers can use the second
    format with separate sections for number of hours, minutes and seconds. The
    format, as regular expression, is ``(\d+h)?[: ]*(\d+m?)[: ]*(\d+s)?``. The
    regular expression expresses an optional number of hours, followed by the
    ``h`` character, followed by any number of spaces or ``:`` characters,
    followed by an optional number of minutes, followed by the ``m`` character,
    again followed by any number of spaces or ``:`` characters, followed by the
    number of seconds, ultimately followed by the ``s`` character.

    The values can no longer be fractional (you cannot say ``2.5m`` you need to
    say ``2m 30s``). We feel that sub-second granularity does is too
    unpredictable to be useful so that will not be supported in the future.

``flags``:
    (optional) This fields contains list of flags separated by spaces or
    commas that might induce plainbox to run the job in particular way.
    Currently, following flags are inspected by plainbox:

    ``preserve-locale``:
        This flag makes plainbox carry locale settings to the job's command. If
        this flag is not set, plainbox will neuter locale settings.  Attach
        this flag to all job definitions with commands that use translations .

    ``win32``:
        This flag makes plainbox run jobs' commands in windows-specific manner.
        Attach this flag to jobs that are run on Windows OS.

    ``noreturn``:
        This flag makes plainbox suspend execution after job's command is run.
        This prevents scenario where plainbox continued to operate (writing
        session data to disk and so on), while other process kills it (leaving
        plainbox session in unwanted/undefined state).
        Attach this flag to jobs that cause killing of plainbox process during
        their operation. E.g. run shutdown, reboot, etc.

.. _job_flag_has_leftovers:

    ``has-leftovers``:
        This flag makes plainbox silently ignore (and not log) any files left
        over by the execution of the command associated with a job. This flag
        is useful for jobs that don't bother with maintenance of temporary
        directories and just want to rely on the one already created by
        plainbox.

.. _job_flag_simple:

    ``simple``:
        This flag makes plainbox disable certain validation advice and have
        some sesible defaults for automated test cases.  This simiplification
        is meant to cut the boiler plate on jobs that are closer to unit tests
        than elaborate manual interactions.

        In practice the following changes are in effect when this flag is set:

         - the *plugin* field defaults to *shell*
         - the *description* field is entirely optional
         - the *estimated_duration* field is entirely optional
         - the *preserve-locale* flag is entirely optional

        A minimal job using the simple flag looks as follows::

            id: foo
            command: echo "Jobs are simple!"
            flags: simple

    Additional flags may be present in job definition; they are ignored.

``imports``:
    (optional) This field lists all the resource jobs that will have to be
    imported from other namespaces. This enables jobs to use resources from
    other namespaces.
    You can use the "as ..." syntax to import jobs that have dashes, slashes or
    other characters that would make them invalid as identifiers and give them
    a correct identifier name. E.g.::

        imports: from 2013.com.canonical.certification import cpuinfo
        requires: 'armhf' in cpuinfo.platform

        imports: from 2013.com.canonical.certification import cpu-01-info as cpu01
        requires: 'avx2' in cpu01.other

    The syntax of each imports line is::

        IMPORT_STMT :: "from" <NAMESPACE> "import" <PARTIAL_ID>
                       | "from" <NAMESPACE> "import" <PARTIAL_ID> AS <IDENTIFIER>

===========================
Extension of the job format
===========================

The Checkbox job format can be considered "extensible", in that
additional keys can be added to existing jobs to contain additional
data that may be needed.

In order for these extra fields to be exposed through the API (i.e. as
properties of JobDefinition instances), they need to be declared as
properties in (`plainbox.impl.job`). This is a good place to document,
via a docstring, what the field is for and how to interpret it.

Implementation note: if additional fields are added, Checkbox needs
to be also told about them, the reason is that Checkbox *does* perform
validation of the job descriptions, ensuring they contain only known fields and
that fields contain expected data types. The jobs_info plugin contains the job
schema declaration and can be consulted to verify the known fields, whether
they are optional or mandatory, and the type of data they're expected to
contain.

Also, Checkbox validates that fields contain data of a specific type,
so care must be taken not to simply change contents of fields if
Checkbox compatibility of jobs is desired.

Plainbox does this validation on a per-accessor basis, so data in each
field must make sense as defined by that field's accessor. There is no need,
however, to declare field type beforehand.
