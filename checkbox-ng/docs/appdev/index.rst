======================
Application developers
======================

This chapter organizes information useful for developers working on testing
systems and :term:`CheckBox` derivatives.

.. warning::

    This chapter is very much under development. The list of stories below is a
    guiding point for subsequent editions that will expand and provide real
    value.

Personas and stories
--------------------

* I'm a CheckBox, CheckBox derivative or third party developer:

    * What use cases should require a new application?
    * How should I be using PlainBox APIs?
    * Which parts of PlainBox APIs are stable?
    * How can I have *special sauce* with using PlainBox at the core?
    * What is covered by CheckBox

* I'm a CheckBox developer.

    * I'm adding a new feature, should that feature go to CheckBox or PlainBox?
    * I'm writing a new job, should that job go to CheckBox or JobBox?

* I'm a developer working on test system different from but not unlike plainbox
  (this is in the same chapter but should heavily link to derivative systems
  and application development chapter)

    * Why would I depend on plainbox rather than do everything I need myself?
    * Do I need to create a derivative or can I just create jobs for what
      plainbox supports?
    * What are the stability guarantees if I choose to build with planbox?
    * How can I use plainbox as a base for my automated or manual testing
      system?
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
