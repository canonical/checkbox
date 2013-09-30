===================================
Checkbox job file format and fields
===================================

This file contains NO examples, this is on purpose since the jobs
directory contains several hundred examples showcasing all the features
described here.

File format and location
------------------------
Jobs are expressed as sections in text files that conform somewhat to
the rfc822 specification format. Each section defines a single job. The
section is delimited with an empty newline. Within each section, each
field starts with the field name, a colon, a space and then the field
contents. Multiple-line fields can be input by having a newline right
after the colon, and then entering text lines after that, each line
should start with at least one space.

Fields that can be used on a job
--------------------------------
:name:
    (mandatory) - A name for the job. Should be unique, an error will
    be generated if there are duplicates. Should contain characters in 
    [a-z0-9/-].
    
:plugin:

    (mandatory) - For historical reasons it's called "plugin" but it's
    better thought of as describing the "type" of job. The allowed types
    are:

     :manual: jobs that require the user to perform an action and then
          decide on the test's outcome.
     :shell: jobs that run without user intervention and
         automatically set the test's outcome.
     :user-interact: jobs that require the user to perform an
         interaction, after which the outcome is automatically set.
     :user-verify: jobs that automatically perform an action or test
         and then request the user to decide on the test's outcome.
     :user-interact-verify: jobs that require the user to perform an
        interaction, run a command after which the user is asked to decide on the
        test's outcome. This is essentially a manual job with a command.
     :attachment: jobs whose command output will be attached to the
         test report or submission.
     :local: a job whose command output needs to be in :term:`CheckBox` job
         format. Jobs output by a local job will be added to the set of
         available jobs to be run.
     :resource: A job whose command output results in a set of rfc822
          records, containing key/value pairs, and that can be used in other
          jobs' ``requires`` expressions.

:requires:
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
    
    The :term:`PlainBox` resource program evaluator is extensively documented,
    to see a detailed description including rationale and implementation of
    :term:`CheckBox` "legacy" compatibility, see :ref:`Resources in Plainbox
    <resources>`.

:depends:
    (optional). If specified, the job will only run if all the listed
    jobs have run and passed. Multiple job names, separated by spaces,
    can be specified.

:command:
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

:description:
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
:user:
    (optional). If specified, the job will be run as the user specified
    here. This is most commonly used to run jobs as the superuser
    (root).

:environ:
    (optional). If specified, the listed environment variables
    (separated by spaces) will be taken from the invoking environment
    (i.e. the one :term:`CheckBox` is run under) and set to that value on the
    job execution environment (i.e.  the one the job will run under).
    Note that only the *variable names* should be listed, not the
    *values*, which will be taken from the existing environment. This
    only makes sense for jobs that also have the ``user`` attribute.
    This key provides a mechanism to account for security policies in
    ``sudo`` and ``pkexec``, which provide a sanitized execution
    environment, with the downside that useful configuration specified
    in environment variables may be lost in the process.

:estimated_duration:
    (optional) This field contains metadata about how long the job is
    expected to run for, as a positive float value indicating
    the estimated job duration in seconds.

===========================
Extension of the job format
===========================

The :term:`CheckBox` job format can be considered "extensible", in that
additional keys can be added to existing jobs to contain additional
data that may be needed.

In order for these extra fields to be exposed through the API (i.e. as
properties of JobDefinition instances), they need to be declared as
properties in (:mod:`plainbox.impl.job`). This is a good place to document,
via a docstring, what the field is for and how to interpret it.

Implementation note: if additional fields are added, *:term:`CheckBox`* needs
to be also told about them, the reason is that :term:`CheckBox` *does* perform
validation of the job descriptions, ensuring they contain only known fields and
that fields contain expected data types. The jobs_info plugin contains the job
schema declaration and can be consulted to verify the known fields, whether
they are optional or mandatory, and the type of data they're expected to
contain.

Also, :term:`CheckBox` validates that fields contain data of a specific type,
so care must be taken not to simply change contents of fields if
:term:`CheckBox` compatibility of jobs is desired.

:term:`PlainBox` does this validation on a per-accessor basis, so data in each
field must make sense as defined by that field's accessor. There is no need,
however, to declare field type beforehand.
