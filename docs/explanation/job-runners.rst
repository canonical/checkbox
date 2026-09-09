.. _job-runners:

How Checkbox runs jobs
======================

Checkbox does more than start the command in a job definition. Before running
it, Checkbox prepares an execution context with the required working directory,
user and environment. It then starts the command, reading its output
and exit code.

Checkbox has two ways to create this execution context: the legacy
subprocess-based runner and the systemd-based runner. They have the same goal,
but they differ in strategy, affecting isolation and, when Checkbox is
installed as a snap, confinement.

Why job isolation matters
-------------------------

A test job is not necessarily a short-lived, well-behaved command. It can put
the system under pressure, change process attributes or leave child
processes behind. These effects should remain local to the job. Otherwise, one
job can affect the Checkbox agent or change the conditions under which later
jobs run.

A cgroup is a Linux mechanism for organising processes and applying resource
accounting and controls to them. Giving each job its own cgroup establishes a
clear boundary between the test workload and Checkbox itself. It also lets
systemd manage the job as a unit rather than as an ordinary child process of
the agent.

The subprocess-based runner
---------------------------

The subprocess-based runner starts the job as a child process of the Checkbox
agent. This is a simple execution model, but the job remains in
the agent's cgroup and inherits many process attributes from it.

Sharing a cgroup means that a job can taint the execution context used by
Checkbox. For example, processes left by one job can remain associated with
the same cgroup in which later jobs run. Additionally systemd processes may not
distinguish between the job and the agent, given they are in the same cgroup,
leading to actions taken on the job affecting the agent as well (for example,
OOMKill)

Snap confinement adds another limitation. A subprocess starts inside both the
Checkbox snap's mount namespace and its AppArmor sandbox. If that subprocess
invokes an application from another snap, the application does not enter its
normal security context as this is effectively not supported. The resulting
security context of this action is effectively undefined behaviour but in most
cases results in the very permissive Checkbox AppArmor profile being applied,
so the other snap's permissions are not enforced as intended.

.. mermaid::

   flowchart LR
     subgraph checkbox[Checkbox execution context]
       agent[Checkbox agent]
       child[Child subprocess]
       command[Job shell]
       agent -->|Spawn with job context| child
       child --> command
       command -->|exit status and output| child
       child --> agent
     end


The systemd-based runner
------------------------

The systemd-based runner delegates process creation to `plz-run`_. ``plz-run``
is a tool similar to ``systemd_run``, it uses systemd to create a transient
unit for the job. The resulting service is not a child of the Checkbox agent
and receives its own cgroup.

For a non-root job, the transient unit uses the ``system-login`` PAM
configuration. This establishes the user session through PAM rather than
merely changing the process user within the Checkbox process tree.

.. mermaid::

   flowchart TB
     subgraph checkbox[Checkbox execution context]
       agent[Checkbox agent]
       request["plz-run"]
       agent --> request
     end

     request -->|D-Bus StartTransientUnit<br/>Job context| systemd[systemd]
     systemd --> unit[Transient unit]

     subgraph job[Job execution context]
       unit --> pam["PAM session<br/>(non-root jobs)"]
       pam --> command[Job shell]
     end

     command -->|exit status and output| unit
     unit --> systemd
     systemd --> request
     request --> agent

On a classic installation, this provides the process and cgroup isolation.
In a strict snap installation, this also crosses the Checkbox
AppArmor boundary. The transient unit runs outside the Checkbox AppArmor
sandbox, while entering the Checkbox snap's mount namespace so that commands
and content supplied by the snap remain valid.

Running outside the Checkbox AppArmor profile does not mean bypassing all
system permissions. The job still runs as its selected user and remains subject
to normal permissions and any security policy applied to programs it starts.
When invoking a snap app, snapd can now correctly apply that snap's own
namespace, AppArmor profile and interface permissions. This is why calls to
other snaps behave correctly, rather than inheriting the Checkbox snap's
confinement.

Comparing the runners
---------------------

.. list-table::
   :header-rows: 1
   :widths: 24 38 38

   * - Property
     - Subprocess-based runner
     - Systemd-based runner
   * - Process relationship
     - Job is a child of Checkbox
     - Job is an independent systemd transient unit
   * - Cgroup
     - Shared with Checkbox
     - Dedicated
   * - User
     - Only the user changes
     - Uses PAM sessions for non-root jobs
   * - Checkbox snap namespace
     - Shared with Checkbox
     - Shared with Checkbox
   * - AppArmor profile
     - Shared with Checkbox
     - None
   * - Invoking other snaps
     - Undefined behaviour - Mostly inherited from Checkbox
     - Normal ``snap run`` behaviour

Defaults
--------

The systemd-based runner is the default runner for snaps. The legacy
subprocess-based runner can be re-enabled by setting the feature flag
:ref:`systemd_based_job_runner <configuration-systemd-based-job-runner>` to
``False``.

.. _plz-run: https://github.com/canonical/plz-run
