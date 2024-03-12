.. _job_status:

Checkbox Job Status
===================

A Checkbox job always receives a final status either automatically or
manually. The following is a description of what each status means and when/how
it is received.

Passed Jobs
------------

The Passing outcome is the marker for a successful run. It can be assigned in
the following situations:

- Automated job returned a 0 return code
- Automated job is marked as ``noreturn`` and the session was interrupted and
  brought back
- Manual job marked as passed by the user
- Job explicitly marked as passed by the user when a session was manually
  brought back after interruption

Every passed job is marked by either the following symbol ``☑`` (ballot box
with check) or the text ``job passed``. Checkbox internally uses the
``IJobResult.OUTCOME_PASS`` object to mark these jobs.

Skipped Jobs
------------

The Skipped outcome is the marker for a job that was intentionally not started
either by the user or Checkbox itself. This can be due to the following
reasons:

- Job with a ``require`` constraint that can not be satisfied
- Job with a dependency on a job that is skipped itself
- Job is ``manual``, ``user-interact`` or ``user-interact-verify`` but the
  session is ``silent``
- Job explicitly skipped by the user via the Ctrl+C menu
- Job explicitly skipped by the user via the resume screen

Every skipped job is either marked by the following symbol ``☐`` (ballot
box) or the text ``job skipped``. Checkbox internally uses the
``IJobResult.OUTCOME_SKIP`` to mark these jobs.

Failed Jobs
------------

The Failing outcome is the marker for a failing job run. It can be assigned in
the following situations:

- Automated job returned a non-0 return code
- Manual job marked as failed by the user
- Job explicitly marked as failed by the user when a session was manually
  brought back after interruption

Every failed job is marked by either the following symbol ``☒``
(ballot box with X) or the text ``job failed``. Checkbox internally
uses the ``IJobResult.OUTCOME_FAIL`` object to mark these jobs.

Crashed Jobs
-------------

The Crashing outcome is the marker for a crashing job. It can only be assigned
to automated job in the following situations:

- Job crashed or was forcibly terminated by an external actor (like the Out of
  Memory Guardian)
- Job interrupted the testing session without a ``noreturn`` flag

Every crashed job is marked by either the warning marker ``⚠`` (warning sign)
or the text ``job crashed``. Checkbox internally uses the
``IJobResult.OUTCOME_CRASH`` object to mark these jobs.

Not Started Jobs
----------------

The Not Started outcome is the marker for a job that can not be started. It is
assigned only in the situation where a job depends on another job that was
either skipped or not started itself.

Every not-started job is marked either by the following marker ``☐`` (ballot
box) or the text ``job cannot be started``. Checkbox internally uses the
``IJobResult.OUTCOME_NOT_SUPPORTED`` object to mark these jobs.
