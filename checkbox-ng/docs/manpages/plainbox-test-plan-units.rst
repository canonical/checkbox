============================
plainbox-test-plan-units (7)
============================

Synopsis
========

This page documents the Plainbox test plan units syntax and runtime behavior

Description
===========

The test plan unit is an evolution of the Plainbox whitelist concept, that is,
a facility that describes a sequence of job definitions that should be executed
together.

As in whitelists, jobs definitions are _selected_ by either listing their
identifier or a regular expression that matches their identifier. Selected
jobs are executed in the sequence they appear in the list, unless they need to
be reordered to satisfy dependencies which always take priority.

Unlike whitelists, test plans can contain additional meta-data which can be
used in a graphical user interface. You can assign a translatable name and
description to each test plan. This used to be done informally by naming the
``.whitelist`` file appropriately, with some unique filename and including
some #-based comments at the top of the file.

Test plans are also typical units so they can be defined with the familiar
RFC822-like syntax that is also used for job definitions. They can also be
multiple test plan definitions per file, just like with all the other units,
including job definitions.

Test Plan Fields
-----------------

The following fields can be used in a test plan. Note that **not all** fields
need to be used or even should be used. Please remember that Checkbox needs to
maintain backwards compatibility so some of the test plans it defines may have
non-typical constructs required to ensure proper behavior. You don't have to
copy such constructs when working on a new test plan from scratch

``id``:
    Each test plan needs to have a unique identifier. This is exactly the same
    as with other units that have an identifier (like job definitions
    and categories).

    This field is not used for display purposes but you may need to refer
    to it on command line so keeping it descriptive is useful

``name``:
    A human-readable name of the test plan. The name should be relatively short
    as it may be used to display a list of test plans to the test operator.

    Remember that the user or the test operator may not always be familiar with
    the scope of testing that you are focusing on. Also consider that multiple
    test providers may be always installed at the same time. The translated
    version of the name (and icon, see below) is the only thing that needs
    to allow the test operator to  pick the right test plan.

    Please use short and concrete names like:
     - "Storage Device Certification Tests"
     - "Ubuntu Core Application's Clock Acceptance Tests"
     - "Default Ubuntu Hardware Certification Tests".

    The field has a soft limit of eighty characters. It cannot have multiple
    lines. This field should be marked as translatable by prepending the
    underscore character (\_) in front. This field is mandatory.

``description``:
    A human-readable description of this test plan. Here you can include as
    many or few details as you'd like. Some applications may offer a way
    of viewing this data. In general it is recommended to include a description
    of what is being tested so that users can make an informed decision but
    please in mind that the ``name`` field alone must be sufficient to
    discriminate between distinct test plans so you don't have to duplicate
    that information in the description.

    If your tests will require any special set-up (procuring external hardware,
    setting some devices or software in special test mode) it is recommended
    to include this information here.

    The field has no size limit. It can contain newline characters. This field
    should be marked as translatable by prepending the underscore character
    (\_) in front. This field is optional.

``include``:
    A multi-line list of job identifiers or patterns matching such identifiers
    that should be included for execution.

    This is the most important field in any test plan. It basically decides
    on which job definitions are selected by (included by) the test plan.
    Separate entries need to be placed on separate lines. White space does not
    separate entries as the id field may (sic!) actually include spaces.

    You have two options for selecting tests:

     - You can simply list the identifier (either partial or fully qualified)
       of the job you want to include in the test plan directly. This is very
       common and most test plans used by Checkbox actually look like that.

     - You can use regular expressions to select many tests at the same time.
       This is the only way to select generated jobs (created either by
       template units or by job definitions using the legacy 'local' plugin
       type). Please remember that the dot character has a special meaning
       so unless you actually want to match *any character* escape the dot
       with the backslash character (\\).

    Regardless of if you use patterns or literal job identifiers you can use
    their fully qualified name (the one that includes the namespace they reside
    in) or an abbreviated form. The abbreviated form is applicable for job
    definitions that reside in the same namespace (but not necessarily the same
    provider) as the provider that is defining the test plan.

    Plainbox will catch incorrect references to unknown jobs so you should
    be relatively safe. Have a look at the examples section below for examples
    on how you can refer to jobs from other providers (you simply use their
    fully qualified name for that)

``mandatory_include``:
    A multi-line list of job identifiers or patterns matching such identifiers
    that should always be executed.

    This optional field can be used to specify the jobs that should always run.
    This is particularly useful for specifying jobs that gather vital
    info about the tested system, as it renders imposible to generate a report
    with no information about system under test.

    For example, session results meant to be sent to the Ubuntu certification
    website must include the special job: miscellanea/submission-resources

    Example:

        mandatory_include:
            miscellanea/submission-resources

    Note that mandatory jobs will always be run first (along with their
    dependant jobs)

``bootstrap_include``:
    A multi-line list of job identifiers that should be run first, before the
    main body of testing begins. The job that should be included in the
    bootstrapping sections are the ones generating or helping to generate other
    jobs.

    Example:

        bootstrap_include:
            graphics/generator_driver_version

    Note that each entry in the bootstrap_include section must be a valid job
    identifier and cannot be a regular expression pattern.
    Also note that only local and resource jobs are allowed in this section.

``exclude``:
    A multi-line list of job identifiers or patterns matching such identifiers
    that should be excluded from execution.

    This optional field can be used to prevent some jobs from being selected
    for execution. It follows the similarly named  ``-x`` command line option
    to the ``plainbox run`` command.

    This field may be used when a general (broad) selection is somehow made
    by the ``include`` field and it must be trimmed down (for example, to
    prevent a specific dangerous job from running). It has the same syntax
    as the ``include``.

    When a job is both included and excluded, exclusion always takes priority.

``category-overrides``:
    A multi-line list of category override statements.

    This optional field can be used to alter the natural job definition
    category association. Currently Plainbox allows each job definition to
    associate itself with at most one category (see plainbox-category-units(7)
    and plainbox-job-units(7) for details). This is sub-optimal as some tests
    can be easily assigned equally well to two categories at the same time.

    For that reason, it may be necessary, in a particular test plan, to
    override the natural category association with one that more correctly
    reflects the purpose of a specific job definition in the context of a
    specific test plan.

    For example let's consider a job definition that tests if a specific piece
    of hardware works correctly after a suspend-resume cycle. Let's assume that
    the job definition  has a natural association with the category describing
    such hardware devices. In one test plan, this test will be associated
    with the hardware-specific category (using the natural association). In
    a special suspend-resume test plan the same job definition can
    be associated with a special suspend-resume category.

    The actual rules as to when to use category overrides and how to assign
    a natural category to a specific test is not documented here. We believe
    that each project should come up with a workflow and semantics that best
    match its users.

    The syntax of this field is a list of statements defined on separate lines.
    Each override statement has the following form::

        apply CATEGORY-IDENTIFIER to JOB-DEFINITION-PATTERN

    Both 'apply' and 'to' are literal strings. CATEGORY-IDENTIFIER is
    the identifier of a category unit. The JOB-DEFINITION-PATTERN has the
    same syntax as the ``include`` field does. That is, it can be either
    a simple string or a regular expression that is being compared to
    identifiers of all the known job definitions. The pattern can be
    either partially or fully qualified. That is, it may or may not
    include the namespace component of the job definition identifier.

    Overrides are applied in order and the last applied override is the
    effective override in a given test plan. For example, given the
    following two overrides::

        apply cat-1 to .*
        apply cat-2 to foo

    The job definition with the partial identifier ``foo`` will be associated
    with the ``cat-2`` category.

``estimated_duration``:
    An approximate time to execute this test plan, in seconds.

    This field is optional. If it is missing it is automatically computed by
    the identical field that may be specified on particular job definitions.

    Since sometimes it is easier to think in terms of test plans (they are
    typically executed more often than a specific job definition) this estimate
    may be more accurate as it doesn't include the accumulated sum of
    mis-estimates from all of the job definitions selected by a particular
    test plan.

Migrating From Whitelists
-------------------------

Migrating from whitelists is optional but strongly recommended. Whitelists
are discouraged but neither deprecated nor unsupported. As we progress on the
transition we are likely to fully deprecate and subsequently remove the
classical form of whitelits (as are typically found in many ``*.whitelist``
files).

The first thing you need to do is to create a file that will hold your test
plans. You should put that file in the ``units/`` directory of your provider.

Note that a file that holds a test plan may also hold any other units.
The decision on how to structure your provider is up to you and the particular
constraints and recommended practices of the project you are participating in.

Having selected an appropriate file simply copy your old whitelist (just one)
and paste it into the _template_ below::

    unit: test plan
    id: << DERIVE A PROPER IDENTIFIER FROM THE NAME OF THE WHITELIST FILE >>
    _name: << COME UP WITH A PROPER NAME OF THIS TEST PLAN >>
    _description:
        << COME UP WITH A PROPER DESCRIPTION OF THIS TEST PLAN >>
    include:
        << PASTE THE FULL TEXT OF YOUR OLD WHITELIST >>

Note that you may also add the ``estimated_duration`` field but this is not
required. Sometimes it is easier to provide a rough estimate of a whole test
plan rather than having to compute it from all the job definitions it selects.

Examples
--------

A simple test plan that selects several jobs::

    id: foo-bar-and-froz
    _name: Tests Foo, Bar and Froz
    _description:
        This example test plan selects the following three jobs:
            - Foo
            - Bar
            - Froz
    include:
        foo
        bar
        froz

A test plan that uses jobs from another provider's namespace in addition
to some of its own definitions::

    id: extended-tests
    _name: Extended Storage Tests (By Corp Inc.)
    _description:
        This test plan runs an extended set of storage tests, customized
        by the Corp Inc. corporation. In addition to the standard Ubuntu
        set of storage tests, this test plan includes the following tests::

        - Multipath I/O Tests
        - Degraded Array Recovery Tests
    include:
        2013.com.canonical.certification:disk/.*
        multipath-io
        degrade-array-recovery

A test plan that generates jobs using bootstrap_include section::

    unit: test plan
    id: test-plan-with-bootstrapping
    _name: Tests with a bootstrapping stage
    _description:
        This test plan uses bootstrapping_include field to generate additional
        jobs depending on the output of the generator job.
    include: .*
    bootstrap_include:
        generator

    unit: job
    id: generator
    plugin: resource
    _description: Job that generates Foo and Bar resources
    command:
     echo "my_resource: Foo"
     echo
     echo "my_resource: Bar"

    unit: template
    template-unit: job
    template-resource: generator
    plugin: shell
    estimated_duration: 1
    id: generated_job_{my_resource}
    command: echo {my_resource}
    _description: Job instantiated from template that echoes {my_resource}



A test plan that marks some jobs as mandatory::
    unit: test plan
    id: test-plan-with-mandatory-jobs
    _name: Test plan with mandatory jobs
    _description:
        This test plan runs some jobs regardless of user selection.
    include:
        Foo
    mandatory_include:
        Bar

    unit: job
    id: Foo
    _name: Foo job
    _description: Job that might be deselected by the user
    plugin: shell
    command: echo Foo job

    unit: job
    id: Bar
    _name: Bar job (mandatory)
    _description: Job that should *always* run
    plugin: shell
    command: echo Bar job
