==============================
plainbox-session-structure (7)
==============================

Synopsis
========

This page documents the structure of the PlainBox per-session directory.

Description
===========

Each session is represented by a directory. Typically all sessions are stored
in the ``$XDG_CACHE_HOME/plainbox/sessions/`` directory.  Each directory there
is a randomly-named session comprised of the following files and directories.

session:
    A state with the serialized state of the session.  Currently it is a JSON
    document compressed with the gzip compression scheme. You can preview the
    contents of this file with ``zcat session | json_pp`` where ``zcat`` (1)
    and `json_pp`` (1) are external system utilities.

    The session file stores the *state* of the session. State is represented by
    several structures which are further documented in
    :doc:`plainbox-session-state`. This file is essential for resuming a
    session but is also useful for debugging.

io-logs:
    A directory with files representing input-output operations performed by
    particular jobs. There are three files for each job. One for PlainBox
    itself and two more for human-readable debugging. The files are:

    \*.record.gz:
        A file internal to PlainBox, containing representation of all of the
        input-output operations performed by the specified job definition's
        command process.

        The format for this file is a gzip-compressed sequence of records,
        represented as separate lines, terminated with the newline character.
        Each record is a small JSON list of exactly three elements. The first
        element is a JSON number representing the delay since the previous
        element was generated OR the delay before the process startup time, for
        the first record. The second name is the name of the communication
        stream. Currently only `stdout` and `stderr` are used. The third and
        last element of each record is a base-64 encoded binary string
        representing the communication that took place.

        The leading part of the filename is currently the identifier of the job
        definition but this is subject to change to allow for multiple log
        files associated with a single job in a given session.

        To figure out which log file is associated with each job definition,
        refer to the state file (``session``).

    \*.stdout:
        Plain-text representation of the entire `stdout` stream as it was
        printed by the command process. This file is purely for debugging and
        is ignored by PlainBox. It may cease to be generated at some future
        time.

    \*.stderr:
        Similarly to ``.stdout`` but for the `stderr` stream.

CHECKBOX_DATA:
    A directory associated with the :doc:`PLAINBOX_SESSION_SHARE` per-session
    runtime directory where jobs may deposit files to perform a primitive form
    of IJC (inter-job-communication).
