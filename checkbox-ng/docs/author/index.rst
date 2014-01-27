=======================
Job and Test Developers
=======================

This chapter organizes information useful for developers creating and
maintaining jobs and test scripts but not directly involved in changing the
core.

.. toctree::
   checkbox-job-format.rst
   whitelists.rst
   providers.rst
   rfc822.rst

Missing Documentation / TODO
============================

.. note::

    This chapter is very much under development. The list of stories below
    is a guiding point for subsequent editions that will expand and provide
    real value.

Personas and stories
--------------------

* I'm a developer working on the checkbox project. With my *job developer* hat
  on:

  * how does plainbox help me do my job when...

    * ... I'm fixing a bug in existing jobs or scripts?
    * ... I'm working on a new job from scratch?
    * ... I'm working on private collection of jobs?

  * how can I check for syntax correctness, simple errors, etc?
  * how can I write automated tests for my jobs?
  * how can I run automated tests for my jobs?
  * how can I document my jobs so that others can understand and use them
    better?

* I'm a developer working on a derivative of the checkbox project. I don't know
  much about plainbox. What should I be aware of and how can I use plainbox to
  do my job better.

  * (same as above but with different assumptions about initial familiarity
    with plainbox)
  * how can I find about all the existing jobs?
  * how can I find about all the existing resource jobs?

* I'm a developer working on test system different from but not unlike plainbox
  (this is in the same chapter but should heavily link to derivative systems
  and application development chapter)

  * Why would I depend on plainbox rather than do everything I need myself?
  * Do I need to create a derivative or can I just create jobs for what
    plainbox supports?
  * What are the stability guarantees if I choose to build with planbox?
  * How can I use plainbox as a base for my automated or manual testing system?
  * How does an example third party test system built on top of plainbox look
    like?

Key topics
----------

.. note::

    The list here should always be based on the personas and stories section
    above.

* Introduction to plainbox
* Where is plainbox getting the jobs from?
* Creating and maintaining jobs with plainbox
