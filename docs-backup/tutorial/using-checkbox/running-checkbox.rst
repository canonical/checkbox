.. _base_tutorial_running:

============================
Running your first test plan
============================

Now that you have Checkbox installed, it's time to use it to execute a
test plan!

A :term:`test plan` is a series of test cases, or :term:`jobs<job>`, that
Checkbox will run one after the other during a test session. Once all of the
jobs have run, a test report is generated, and the test results can optionally
be uploaded to the :term:`Canonical test database<certification website>`.

Running Checkbox and filtering test plans
=========================================

Let's begin! Run the following command to start Checkbox:

.. code-block:: none

    checkbox.checkbox-cli

You will be greeted with the same screen as in the previous page:


.. code-block:: none

  Select test plan
  ┌─────────────────────────────────────────────────────────────────────────────────────┐
  │ ( ) (Deprecated) Fully Automatic Client Certification Tests                         │
  │ ( ) 18.04 Server Certification Full                                                 │
  │ ( ) 18.04 Server Certification Functional                                           │
  │ ( ) 18.04 System On Chip Certification (For SoC Testing)                            │
  │ ( ) 18.04 Virtual Machine Full (For Hypervisors)                                    │
  │ ( ) 20.04 Server Certification Full                                                 │
  └─────────────────────────────────────────────────────────────────────────────────────┘
  Press <Enter> to continue                                                      (H) Help

This is the test plan selection screen. You can use the ``up`` and ``down``
arrow keys to navigate through all the test plans bundled by default with
Checkbox.  As you can see, there are a lot! Let's filter the list. Press the
``f`` key to filter the list. The bottom line of the screen becomes:

.. code-block:: none

    filter:

Type ``Tutorial`` (with an uppercase ``T``) and press ``Enter`` to validate.
All of a sudden, the list becomes much less intimidating!

.. code-block:: none

     Select test plan
    ┌──────────────────────────────────────────────────────────────────────────────┐
    │                                                                              │
    │    ( ) Checkbox Base Tutorial Test Plan                                      │
    │    ( ) Checkbox Base Tutorial Test Plan (using manifest)                     │
    │                                                                              │
    └──────────────────────────────────────────────────────────────────────────────┘
     Press <Enter> to continue                                             (H) Help

Selecting a test plan and the jobs to run
=========================================

Using the arrow keys, highlight the first line (``Checkbox Base Tutorial
Test Plan``).  Press ``Space`` to select it, and ``Enter`` to validate. You
can now see the list of jobs in the test plan you selected:

.. code-block:: none

     Choose tests to run on your system:
    ┌──────────────────────────────────────────────────────────────────────────────┐
    │[X] + Tutorial                                                                │
    │                                                                              │
    └──────────────────────────────────────────────────────────────────────────────┘
     Press (T) to start Testing                                            (H) Help

The jobs are grouped by categories, and by default each category is folded
so that it's easier to see at a glance what is going to be run. In this test
plan, there is only one category, ``Tutorial``. Let's open it to see what's
inside. With the category highlighted, press ``Enter``:

.. code-block:: none

     Choose tests to run on your system:
    ┌──────────────────────────────────────────────────────────────────────────────┐
    │[X] - Tutorial                                                                │
    │[X]    A job that always crashes                                              │
    │[X]    A job that displays an environment variable, if set                    │
    │[X]    A job that always fails                                                │
    │[X]    A job that is skipped because it depends on a job that fails           │
    │[X]    A job that requires a resource and it is available                     │
    │[X]    A manual job                                                           │
    │[X]    A job that requires a resource but it's not available                  │
    │[X]    A job that always passes                                               │
    │[X]    A job that depends on other job that passes                            │
    │[X]    A semi-automated job where the outcome is set automatically            │
    │[X]    A semi-automated job where the user manually sets the outcome          │
    │[X]    A job that generates different resources for tutorial purposes         │
    │                                                                              │
    └──────────────────────────────────────────────────────────────────────────────┘
     Press (T) to start Testing                                            (H) Help

Now we have some idea of what is going to be executed. Note that, by default,
all the jobs in the test plan are selected (you can see the ``[X]`` mark next
to them). You can toggle a job selection by highlighting it and pressing the
``space`` key. If you do this while highlighting a category, all the jobs
in this category will be (de)selected. Finally, try to press the ``d``
key. What happened? All the jobs have been deselected! Press the ``s``
key to select them all again.

Press ``t`` to start the test run. A few automated jobs will be executed,
and their outcome automatically set before Checkbox moves on to the next one:

.. code-block:: none

    ========[ Running job 1 / 11. Estimated time left (at least): 0:03:00 ]=========
    --------------------------[ A job that always passes ]--------------------------
    ID: com.canonical.certification::tutorial/passing
    Category: com.canonical.certification::tutorial
    ... 8< -------------------------------------------------------------------------
    This job passes!
    ------------------------------------------------------------------------- >8 ---
    Outcome: job passed
    ========[ Running job 2 / 11. Estimated time left (at least): 0:03:00 ]=========
    --------------------------[ A job that always fails ]---------------------------
    ID: com.canonical.certification::tutorial/failing
    Category: com.canonical.certification::tutorial
    ... 8< -------------------------------------------------------------------------
    This job fails!
    ------------------------------------------------------------------------- >8 ---
    Outcome: job failed
    (...)

For each job, we can see:

- The number of jobs that have run (2) and the total number of jobs scheduled (11)
- The estimated time before the test session is finished (3 minutes)
- The summary of the job ("A job that always fails")
- The unique identifier for this job (``com.canonical.certification::tutorial/failing``)
- The category identifier the job falls into
- The output generated by the job commands ("This job fails!")
- The outcome of the job

Handling interactive jobs
=========================

After a few seconds, you will see the following:

.. code-block:: none

    ========[ Running job 9 / 11. Estimated time left (at least): 0:03:00 ]=========
    --------------------------------[ A manual job ]--------------------------------
    ID: com.canonical.certification::tutorial/manual
    Category: com.canonical.certification::tutorial
    Purpose:
    
    This is a manual job. User needs to select an outcome.
    
    Steps:
    
    1. Read the content of this job.
    2. Check that there are 3 sections (Purpose, Steps, Verification).
    
    Outcome: job needs verification
    Verification:
    
    Did Checkbox display all 3 sections of the manual job?
    
    Please decide what to do next:
      outcome: job needs verification
      comments: none
    Pick an action
      c => add a comment
      p => set outcome to pass
      f => set outcome to fail
      s => set outcome to skip
    [cpfs]: 

This is a manual job. Checkbox provides some explanation and is waiting for
the user to provide feedback.

Let's skip this test for now. Press ``s`` followed by ``Enter``.

Checkbox moves on to the next job, which is a semi-automated one:

.. code-block:: none

    ========[ Running job 10 / 11. Estimated time left (at least): 0:02:00 ]========
    --------[ A semi-automated job where the outcome is set automatically ]---------
    ID: com.canonical.certification::tutorial/user-interact
    Category: com.canonical.certification::tutorial
    Purpose:
    
    This is a "user-interact" semi-automated job. It requires the user to perform
    an interaction, after which the outcome is automatically set and Checkbox moves
    on to the next job.
    
    This test will run the command `true`, which always returns 0.
    
    Steps:
    
    1. Read the content of this job.
    2. Press Enter to start the test. The outcome will be set automatically to
    "pass" based on the return value from the command, and Checkbox will then
    move on to the next job.
    
    Pick an action
        => press ENTER to continue
      c => add a comment
      s => skip this job
      q => save the session and quit
    [csq]: 

This time, you cannot set the outcome directly. Follow the instructions by
pressing ``Enter`` to start the test, and notice that the job is marked as
"passed" and Checkbox moves on to the last job in the list:

.. code-block:: none

    ========[ Running job 11 / 11. Estimated time left (at least): 0:01:00 ]========
    -------[ A semi-automated job where the user manually sets the outcome ]--------
    ID: com.canonical.certification::tutorial/user-interact-verify
    Category: com.canonical.certification::tutorial
    Purpose:
    
    This is a "user-interact-verify" semi-automated job. It requires the user
    to perform an interaction, then Checkbox executes a command and suggests
    an outcome based its return code. However, in the end it is up to the user
    to manually choose the right outcome.
    
    This test will run the command `true`, which always returns 0.
    
    Steps:
    
    1. Read the content of this job.
    2. Press Enter to start the test. The outcome will be automatically set to
    "pass" but you will have a chance to manually select another outcome.
    
    Pick an action
        => press ENTER to continue
      c => add a comment
      s => skip this job
      q => save the session and quit
    [csq]: 

This is another type of semi-automated job. Press ``Enter`` to run it:

.. code-block:: none

    Outcome: job needs verification
    Verification:
    
    Make sure that Checkbox suggested the outcome to be "pass", yet you can
    still manually select another outcome.
    
    Please decide what to do next:
      outcome: job needs verification
      comments: none
    Pick an action
      c => add a comment
      p => set outcome to pass
      f => set outcome to fail
      s => set outcome to skip
      r => re-run this job
        => set suggested outcome [job passed]
    [cpfsr]: 

Notice the two new actions available:

- re-run this job
- set suggested outcome [job passed]

Since Checkbox did what is explained in the "Verification" section of the
job, you can mark this job as passed by pressing ``Enter`` directly.

Re-running failed jobs
======================

You will be taken to the following screen:

.. code-block:: none

    Select jobs to re-run
    ┌──────────────────────────────────────────────────────────────────────────────┐
    │[ ] - Crashed Jobs                                                            │
    │[ ]    - Tutorial                                                             │
    │[ ]       A job that always crashes                                           │
    │[ ] - Failed Jobs                                                             │
    │[ ]    - Tutorial                                                             │
    │[ ]       A job that always fails                                             │
    │[ ] - Jobs with failed dependencies                                           │
    │[ ]    - Tutorial                                                             │
    │[ ]       A job that is skipped because it depends on a job that fails        │
    │[ ]       A job that requires a resource but it's not available               │
    │[ ] - Skipped Jobs                                                            │
    │[ ]    - Tutorial                                                             │
    │[ ]       A manual job                                                        │
    └──────────────────────────────────────────────────────────────────────────────┘
     Press (R) to Rerun selection, (F) to Finish                            (H) Help

Checkbox gives you the opportunity to re-run jobs that may have failed for
various reasons. Using the ``up`` and ``down`` arrow key, navigate to the
manual job that we skipped earlier and select it by pressing ``space``. Now,
press ``r`` to re-run this job. You will see the same screen as earlier,
ending with:

.. code-block:: none

    Pick an action
      c => add a comment
      p => set outcome to pass
      f => set outcome to fail
      s => set outcome to skip
    [cpfs]: 

Adding comments
===============

Let's add a comment to explain what we did. Press ``c`` followed by
``Enter``, and enter the following comment: "This job can now be marked as
passed". Validate by pressing ``Enter`` one more time:

.. code-block:: none

    Please decide what to do next:
      outcome: job needs verification
      comments: This job can now be marked as passed
    Pick an action
      c => add a comment
      p => set outcome to pass
      f => set outcome to fail
      s => set outcome to skip
    [cpfs]: 

You can see your comment has been saved. Press ``p`` and ``Enter`` to mark
this job as passed. You are taken back to the jobs re-run screen, but this
time, the manual job is not here anymore since it was marked as passed.

Reviewing the test session
==========================

Press ``f`` to finish the test session.

You will see the following:

.. code-block:: none

     ☑ : A job that always passes
     ☒ : A job that always fails
     ⚠ : A job that always crashes
     ☑ : A job that depends on other job that passes
     ☐ : A job that is skipped because it depends on a job that fails
     ☑ : A job that generates different resources for tutorial purposes
     ☑ : A job that requires a resource and it is available
     ☐ : A job that requires a resource but it's not available
     ☑ : A job that displays an environment variable, if set
     ☑ : A manual job
      history: job skipped, job passed
     ☑ : A semi-automated job where the outcome is set automatically
     ☑ : A semi-automated job where the user manually sets the outcome

This is the summary of the test session. It will list each job and its outcome.
Here is a table that summarizes the different outcomes a job can have and
their symbols:

.. list-table::
    :header-rows: 1
    :widths: 40 60

    * - symbol
      - outcome
    * -
      - job didn't run
    * - ☑
      - job passed
    * - ☒
      - job failed
    * - ☐
      - job skipped, job cannot be started
    * - ‒
      - job is not implemented
    * - ⁇
      - job needs verification
    * - ⚠
      - job crashed

For jobs that have been re-run, you can see a history of their outcomes. For
instance, the manual job was first skipped, then passed.

Under the summary, you can see 3 additional lines:

.. code-block:: none

    file:///home/user/.local/share/checkbox-ng/submission_2023-09-06T03.33.14.551448.html
    file:///home/user/.local/share/checkbox-ng/submission_2023-09-06T03.33.14.551448.junit.xml
    file:///home/user/.local/share/checkbox-ng/submission_2023-09-06T03.33.14.551448.tar.xz

These are the test reports and submission archives generated by Checkbox
for this run.

You will also be asked if you want to submit the report. You can mark `no` for
the moment by pressing ``n`` and then hitting ``Enter``.

As text summary only provides an overview, for more in-depth
information, you will need to review submission files (the files such as
``submission_2023-09-06T03.33.14.551448.tar.xz`` in the output above).
We will see that in the next section.

Wrapping up
===========

Congratulations! You've got familiar with Checkbox user interface by launching
it, selecting a specific test plan and executing the jobs in it. Once the
test session was over, Checkbox displayed a summary of the results and
generated a bunch of "submission" files. In the next section, you will review
these files.
