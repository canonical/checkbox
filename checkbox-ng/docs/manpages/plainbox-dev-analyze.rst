========================
plainbox-dev-analyze (1)
========================

.. argparse::
    :ref: plainbox.impl.box.get_parser_for_sphinx
    :prog: plainbox
    :path: dev analyze
    :manpage:
    :nodefault:

    The ``plainbox dev analyze`` command is a direct replacement for ``plainbox
    run`` that doesn't really run most of the jobs. Instead it offers a set of
    reports that can be enabled (confusingly, by default no reports are enabled
    and the command prints nothing at all) to inspect certain aspects of the
    hypothetical session

    The only exception to the rule above is the ``--run-local`` option. With that
    option all local jobs and their dependencies *are* started. This is
    technically required to correctly emulate the behavior of ``plainbox run``
    that does so unconditionally. Still, local jobs can cause harm so don't run
    untrusted code this way (the author of this man page recalls one local job
    that ran ``sudo reboot`` to measure bootchart data)

    Report Types
    ============

    Plainbox ``dev analyze`` command offers a number of reports that can be
    selected with their respective command line options. By default, no reports
    are enabled which may be a little bit confusing but all options can be
    enabled at the same time.

    Dependency Report
    -----------------

    This report shows if any of the jobs have missing dependencies. It almost
    never happens but the report is here for completeness.

    Interactivity Report
    --------------------

    This report shows, for each job, if it is fully automatic or if it requires
    human interaction.

    Estimated Duration Report
    -------------------------

    This report shows if Plainbox would be able to accurately estimate the
    duration of the session. It shows details for both fully automatic and
    interactive jobs.

    Validation Report
    -----------------

    This report shows if all of the selected jobs are valid. It is of lesser
    use now that we have provider-wide validation via ``./manage.py validate``

    Two Kinds of Job Lists
    ======================

    Desired Job List
    ----------------

    This list is displayed with the ``-S`` option. It contains the ordered
    sequence of jobs that are "desired" by the test operator to execute.  This
    list contrasts with the so-called `run list` mentioned below.

    Run List
    --------

    This list is displayed with the ``-R`` option. It contains the ordered
    sequence of jobs that should be executed to satisfy the `desired list`
    mentioned above. It is always a superset of the desired job list and almost
    always includes additional jobs (such as resource jobs and other
    dependencies)

    The run list is of great importance. Most of the time the test operator will
    see tests in precisely this order. The only exception is that some test
    applications choose to pre-run local jobs. Still, if your job ordering is
    wrong in any way, inspecting the run list is the best way to debug the
    problem.

See Also
========

:doc:`plainbox-run`
