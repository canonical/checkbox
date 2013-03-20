PlainBox Architecture
=====================

This document explains the architecture of PlainBox internals. It should be
always up-to-date and accurate to the extent of the scope of this overview.

General design considerations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

PlainBox is a reimplementation of CheckBox that replaces a reactor / event /
plugin architecture with a monolithic core and tightly integrated components.

The implementation models a few of the externally-visible concepts such as
jobs, resources and resource programs but also has some additional design that
was not present in CheckBox before.

The goal of the rewrite is to provide the right model and APIs for user
interfaces in order to build the kind of end-user solution that we could not
build with CheckBox.

This is expressed by additional functionality that is there only to provide the
higher layers with the right data (failure reason, descriptions, etc.). The
code is also intended to be highly testable. Test coverage at the time of
writing this document was exceeding 80%

The core requirement for the current phase of PlainBox development is feature
parity with CheckBox and gradual shift from one to another in the daily
responsibilities of the Hardware Certification team. Currently PlainBox
implements a large chunk of core / essential features from CheckBox. While not
all features are present the core is considered almost feature complete at this
stage.

Application Skeleton
^^^^^^^^^^^^^^^^^^^^

This skeleton represents a typical application based on PlainBox. It enumerates
the essential parts of the APIs from the point of view of an application
developer.

1. Instantiate :class:`plainbox.impl.checkbox.CheckBox` then call
   :meth:`plainbox.impl.checkbox.CheckBox.get_builtin_jobs()` to discover all
   known jobs. In the future this might be replaced by a step that obtains jobs
   from a named provider.

3. Instantiate :class:`plainbox.impl.runner.JobRunner` so that we can run jobs

4. Instantiate :class:`plainbox.impl.session.SessionState` so that we can keep
   track of application state.

   - Potentially restore an earlier, interrupted, testing session by calling
     :meth:`plainbox.impl.session.SessionState.restore()`

   - Potentially remove an earlier, interrupted, testing session by calling
     :meth:`plainbox.impl.session.SessionState.discard()`

   - Potentially start a new test session by calling
     :meth:`plainbox.impl.session.SessionState.open()`

5. Allow the user to select jobs that should be executed and update session
   state by calling
   :meth:`plainbox.impl.session.SessionState.update_desired_job_list()`

6. For each job in :attr:`plainbox.impl.SessionState.run_list`:

   1. Check if we want to run the job (if we have a result for it from previous
      runs) or if we must run it (for jobs that cannot be persisted across
      suspend)

   2. Check if the job can be started by looking at
      :meth:`plainbox.impl.session.JobState.can_start()`

      - optionally query for additional data on why a job cannot be started and
        present that to the user.

      - optionally abort the sequence and go to step 5 or the outer loop.

   3. Call :meth:`plainbox.impl.runner.JobRunner.run_job()` with the current
      job and store the result.

        - optionally ask the user to perform some manipulation

        - optionally ask the user to qualify the outcome

        - optionally ask the user for additional comments

   4. Call :meth:`plainbox.impl.session.SessionState.update_job_result()` to
      update readiness of jobs that depend on the outcome or output of current
      job.

   5. Call :meth:`plainbox.impl.session.SessionState.checkpoint()` to ensure
      that testing can resume after system crash or shutdown.

7. Instantiate the selected state exporter, for example
   :class:`plainbox.impl.exporters.json.JSONSessionStateExporter` so that we
   can use it to save test results.

    - optionally pass configuration options to customize the subset and the
      presentation of the session state

8. Call
   :meth:`plainbox.impl.exporters.SessionStateExporterBase.get_session_data_subset()`
   followed by :meth:`plainbox.impl.exporters.SessionStateExporterBase.dump()`
   to save results to a file.

9. Call :meth:`plainbox.impl.session.SessionState.close()` to remove any
   nonvolatile temporary storage that was needed for the session.

Essential classes
=================

:class:`~plainbox.impl.session.SessionState`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Class representing all state needed during a single program session.

Usage
-----

The general idea is that you feed the session with a list of known jobs and
a subset of jobs that you want to run and in return get an ordered list of
jobs to run.

It is expected that the user will select / deselect and run jobs. This
class can react to both actions by recomputing the dependency graph and
updating the read states accordingly.

As the user runs subsequent jobs the results of those jobs are exposed to
the session with :meth:`update_job_result()`. This can cause subsequent
jobs to become available (not inhibited by anything). Note that there is no
notification of changes at this time.

The session does almost nothing by itself, it learns about everything by
observing job results coming from the job runner
(:class:`plainbox.impl.runner.JobRunner`) that applications need to
instantiate.

Suspend and resume
------------------

The session can save check-point data after each job is executed. This
allows the system to survive and continue after a catastrophic failure
(broken suspend, power failure) or continue across tests that require the
machine to reboot.

.. todo::

    Create a section on suspend/resume design

Implementation notes
--------------------

Internally it ties into :class:`plainbox.impl.depmgr.DependencySolver` for
resolving dependencies. The way the session objects are used allows them to
return various problems back to the UI level - those are all the error
classes from :mod:`plainbox.impl.depmgr`:

    - :class:`plainbox.impl.depmgr.DependencyCycleError`

    - :class:`plainbox.impl.depmgr.DependencyDuplicateError`

    - :class:`plainbox.impl.depmgr.DependencyMissingError`

Normally *none* of those errors should ever happen, they are only provided
so that we don't choke when a problem really happens. Everything is checked
and verified early before starting a job so typical unit and integration
testing should capture broken job definitions (for example, with cyclic
dependencies) being added to the repository.

Implementation issues
---------------------

There are two issues that are known at this time:

* There is too much checkbox-specific knowledge which really belongs
  elsewhere. We are working to remove that so that non-checkbox jobs
  can be introduced later. There is a branch in progress that entirely
  removes that and moves it to a new concept called SessionController.
  In that design the session delegates understanding of results to a
  per-job session controller and exposes some APIs to alter the state
  that was previously internal (most notably a way to add new jobs and
  resources).

* The way jobs are currently selected is unfortunate because of local jobs
  that can add new jobs to the system. This causes considerable complexity
  at the application level where the application must check if each
  executed job is a 'local' job and re-compute the desired_job_list. This
  should be replaced by a matcher function that can be passed to
  SessionState once so that desired_job_list is re-evaluated internally
  whenever job_list changes.


:class:`~plainbox.impl.job.JobDefinition`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:term:`CheckBox` has a concept of a :term:`job`. Jobs are named units of
testing work that can be executed. Typical jobs range from automated CPU power
management checks, BIOS tests, semi-automated peripherals testing to all manual
validation by following a script (intended for humans).

Jobs are distributed in plain text files, formated as a loose RFC822 documents
where typically a single text file contains a few dozen different jobs that
belong to one topic, for example, all bluetooth tests.

Tests have a number of properties that will not be discussed in detail here,
they are all documented in :class:`plainbox.impl.job.JobDefinition`. From the
architecture point of view the four essential properties of a job are *name*,
*plugin* and *requires* and *depends*. Those are discussed in detail below.

JobDefinition.name
------------------

The *name* field must be unique and is referred to by other parts of the system
(such as whitelists). Typically jobs follow a simple naming pattern
'category/detail', eg, 'networking/modem_connection'. The name must be _unique_
and this is enforced by the core.

JobDefinition.plugin
--------------------

The *plugin* field is an archaism from CheckBox and a misnomer (as PlainBox
does not have any plugins). In the CheckBox architecture it would instruct the
core which plugin should process that job. In PlainBox it is a way to encode
what type of a job is being processed. There is a finite set of types that are
documented below. 

plugin == "shell"
#################

This value is used for fully automated jobs. Everything the job needs to do is
automated (preparation, execution, verification) and fully handled by the
command that is associated with a job.

plugin == "manual" 
##################

This value is used for fully manual jobs. It has no special handling in the core
apart from requiring a human-provided outcome (pass/fail classification) 

plugin == "local"
#################

This value is used for special job generator jobs. The output of such jobs is
interpreted as additional jobs and is identical in effect to loading such jobs
from a job definition file. 

There are two practical uses for such jobs:

* Some local jobs are used to generate a number of jobs for each object.
  This is needed where the tested machine may have a number of such objects
  and each requires unique testing. A good example is a computer where all
  network tests are explicitly "instantiated" for each network card
  present.
 
  This is a valid use case but is rather unfortunate for architecture of
  PlainBox and there is a desire to replace it with equally-expressive
  pattern jobs. The advantage is that unlike local jobs (which cannot be
  "discovered" without enduring any potential side effects that may be
  caused by the job script command) pattern jobs would allow the core to
  determine the names of jobs that can be generated and, for example,
  automatically determine that a pattern job needs to be executed as a
  dependency of a phantom (yet undetermined) job with a given name.

  The solution with "pattern" jobs may be executed in future phases of
  PlainBox development. Currently there is no support for that at all.

  Currently PlainBox cannot determine job dependencies across local jobs.
  That is, unless a local job is explicitly requested (in the desired job
  list) PlainBox will not be able to run a job that is generated by a local
  job at all and will treat it as if that job never existed.

* Some local jobs are used to create a form of informal "category".
  Typically all such jobs have a leading and trailing double underscore,
  for example '__audio__'. This is currently being used by CheckBox for
  building a hierarchical tree of tests that the user may select.

  Since this has the same flaws as described above (for pattern jobs) it
  will likely be replaced by an explicit category field that can be
  specified each job.

plugin == "resource"
####################

This value is used for special "data" or "environment" jobs. Their output is
parsed as a list of RFC822 records and is kept by the core during a testing session.

They are primarily used to determine if a given job can be started. For
example, a particular bluetooth test may use the _requires_ field to indicate
that it depends (via a resource dependency) on a job that enumerates devices
and that one of those devices must be a bluetooth device.

plugin == "user-interact"
#########################

For all intents and purposes it is equivalent to "manual". The actual
difference is that a user is expected to perform some physical manipulation
before an automated test.

plugin == "user-verify"
#######################

For all intents and purposes it is equivalent to "manual". The actual
difference is that a user is expected to perform manual verification after an
automated test.

JobDefinition.depends
---------------------

The *depends* field is used to express dependencies between two jobs. If job A
has depends on job B then A cannot start if B is not both finished and
successful. PlainBox understands this dependency and can automatically sort and
execute jobs in proper order. In many places of the code this is referred to as
a "direct dependency" (in contrast to "resource dependency")

The actual syntax is not strictly specified, PlainBox interprets this field as
a list of tokens delimited by comma or any whitespace (including newlines).

A job may depend on any number of other jobs. There are a number of failure
modes associated with this feature, all of which are detected and handled by
PlainBox. Typically they only arise when during CheckBox job development
(editing actual job files) and are always a sign of a human error. No released
version of CheckBox or PlainBox should ever encounter any of those issues.

The actual problems are:

* dependency cycles, where job either directly or indirectly depends on
  itself

* missing dependencies where some job refers to a job that is not defined
  anywhere.

* duplicate jobs where two jobs with the same name (but different
  definition) are being introduced to the system.

In all of those cases the core removes the offending job and tries to work
regardless of the problem. This is intended more as a development aid rather
than a reliability feature as no released versions of either project should
cause this problem.

JobDefinition.command
---------------------

The *command* field is used when the job needs to call an external command.
Typically all shell jobs define a command to run.

"Manual" jobs can also define a command to run as part of the test procedure.

JobDefinition.user
------------------

The *user* field is used when the job requires to run as a specific user
(e.g. root).

The job command will be run via pkexec to get the necessary
permissions.

JobDefinition.environ
---------------------

The *environ* field is used to pass additional environmental keys from the user
session to the new environment set up when the job command is run by another
user (root, most of the time).

The actual syntax is not strictly specified, PlainBox interprets this field as
a list of tokens delimited by comma or any whitespace (including newlines).
