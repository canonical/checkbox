.. _setup-job:

==============
Setup job unit
==============

A setup job unit is a job that prepares the device under test before the main
body of testing begins. Setup jobs are commonly used to install dependencies or
perform other one-time preparation required by regular jobs in a test plan.

Setup jobs are selected through the ``setup_include`` field of a
:doc:`test-plan`. Only setup job units are valid in ``setup_include``.

Fields
======

The following fields may be used by the setup job unit:

.. program:: setup-job

.. option:: unit

    (mandatory) - The unit type. For setup jobs this must be ``setup job``.

.. option:: id

    (mandatory) - A name for the setup job. Should be unique, an error will be
    generated if there are duplicates. Should contain characters in
    ``[a-z0-9/-]``.

.. option:: summary

    (optional) - A human readable name for the setup job. This value is
    available for translation into other languages. It is used when listing
    jobs. It must be one line long, ideally it should be short (50-70
    characters max).

.. option:: category_id

    (optional) - Identifier of the :doc:`category` this setup job belongs to.

.. option:: plugin

    (optional) - For historical reasons it is called "plugin" but it is better
    thought of as describing the "type" of job. If omitted when the ``simple``
    flag is used, it defaults to ``shell``. The allowed values are:

    .. option:: shell

        Jobs that run without user intervention and automatically set the test's
        outcome.

.. option:: command

    (mandatory) - Command to execute to run the job.

    The command will be executed unconditionally as soon as the job is started.
    The exit code from the command (``0`` for success, ``!0`` for failure)
    will be used to set the test outcome.

    The command will be run using the default system shell. If a specific shell
    is needed it should be instantiated in the command.

    It is recommended to call a python script rather than writing a multi-line
    command.

.. option:: user

    (optional) - If specified, the setup job will be run as the user specified
    here. This is most commonly used to run jobs as the superuser (root).

.. option:: environ

    (optional) - If specified, the listed environment variables (separated by
    spaces) will be taken from the invoking environment (i.e. the one Checkbox
    is run under) and set to that value on the job execution environment (i.e.
    the one the setup job will run under). Note that only the *variable names*
    should be listed, not the *values*, which will be taken from the existing
    environment.

.. option:: estimated_duration

    (optional) - This field contains metadata about how long the setup job is
    expected to run for, as a positive float value indicating the estimated job
    duration in seconds.

    This field can also be expressed with separate sections for the number of
    hours, minutes and seconds. The format, as regular expression, is
    ``(\d+h)?[: ]*(\d+m)?[: ]*(\d+s)?``. For example, ``1h 2m 30s`` or ``5m``.

.. option:: flags

    (optional) - This field contains a list of flags separated by spaces or
    commas that might induce Checkbox to run the setup job in particular way.
    Currently, the following flags are accepted by the setup job schema:

    .. option:: reset-locale

        This flag makes Checkbox reset locale before running the job.

    .. option:: preserve-locale

        This flag makes Checkbox preserve the current locale before running the
        job.

    .. option:: noreturn

        This flag makes Checkbox suspend execution after job's command is run.
        This prevents scenarios where Checkbox continues to operate while
        another process kills it, leaving Checkbox session in unwanted or
        undefined state. Attach this flag to jobs that cause killing of Checkbox
        process during their operation, such as shutdown or reboot jobs.

    .. option:: has-leftovers

        This flag makes Checkbox silently ignore, and not log, any files left
        over by the execution of the command associated with a job.

    .. option:: simple

        This flag makes Checkbox disable certain validation advice and have some
        sensible defaults for automated test cases. In setup jobs, it can imply
        the ``shell`` plugin when ``plugin`` is not specified.

        A minimal setup job using the simple flag looks as follows::

            unit: setup job
            id: setup/foo
            command: echo "Setup jobs can be simple!"
            flags: simple

    .. option:: preserve-cwd

        This flag makes Checkbox run the job command in the current working
        directory without creating a temporary folder and running the command
        from this temporary folder.

.. note::
    Setup job units intentionally support fewer fields than regular
    :doc:`job` units. They do not support ``requires``, ``depends``, ``after``,
    ``before``, ``group``, ``salvages``, ``purpose``, ``steps``,
    ``verification`` or ``siblings``.
