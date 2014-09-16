==========================
PLAINBOX_SESSION_SHARE (7)
==========================

Synopsis
========

Saving files to session share directory::

    ``command: do-something > $PLAINBOX_SESSION_SHARE/some-action.log``

Loading files from session-share directory::

    ``command: cat $PLAINBOX_SESSION_SHARE/some-action.log``

Description
===========

Plainbox sessions allow jobs to communicate by referring to the
$PLAINBOX_SESSION_SHARE environment variable. Files generated
therein are explicitly meant to be accessible to all the other jobs
participating in the session.

Typical Use Cases
-----------------

Typically a session will involve one or more pairs of jobs such as::

    id: some-action
    plugin: shell
    summary: do something and save the log file to disk
    commmand: do-something > $PLAINBOX_SESSION_SHARE/some-action.log

    id: some-action-attachment
    plugin: attachment
    summary: log file of the do-something command
    command: cat $PLAINBOX_SESSION_SHARE/some-action.log

The job ``some-action`` will use the ``do-something`` executable
to perform some tests. The log file of that action will be saved on
the device executing the test, in the directory exposed through the
environment variable ``$PLAINBOX_SESSION_SHARE``.

The ``some-action-attachment`` job will use that same directory and
the agreed-upon name of the log file and ``cat`` (1) it, which coupled
with the plugin type `shell` will cause Plainbox to attach the log
file to the resulting document.

Checkbox Compatibility
----------------------

Jobs designed to work with pre-Plainbox-based Checkbox may still refer
to the old, somewhat confusing, environment variable
``$CHECKBOX_DATA``. It points to the same directory.

Multi-Node Sessions
-------------------

When a test session involves multiple devices this directory is
separately instantiated for each device. Jobs executing on separate
devices cannot use this facility to communicate. If communication
is required jobs are expected to use the LAVA-inspired, MPI-based
communication API. For details see ``plainbox-multi-node-api`` (7)

Bugs
====

Within the session directory the name of this directory is still
``CHECKBOX_DATA`` (literally, this is not a variable name). It may be changed
at any point in time since jobs cannot form any meaningful paths to this
directory without referring to either ``$PLAINBOX_SESSION_SHARE`` or
``$CHECKBOX_DATA``

See Also
========

:doc:`PLAINBOX_PROVIDER_DATA`, :doc:`CHECKBOX_DATA`
