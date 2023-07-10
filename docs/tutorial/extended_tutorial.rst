.. _adv_tutorials: 

=================
Extended Tutorial
=================

Hacking basics
==============

Link here to the QA tutorial for “normal users” and recall that we offer
snaps and debs. The
`CONTRIBUTING.md <https://github.com/canonical/checkbox/blob/main/CONTRIBUTING.md>`__
guide is a good basic as it explains how to install, sideload and launch
both remotely and locally, how to create new providers etc..

   Basic -> Only use the most common options, think of ``name`` not
   ``category-overrides``

Basic Test Plan
===============

Create a simple test plan that includes a few test cases from tutorial
or smoke, for example, to get the hang of it.

Recall here side-loading.

Outcome: Run the created test plan, show output

Basic Test Case
===============

Now that we know how to create a custom test plan, lets create a custom
test case.

Auto Test Case
--------------

Introduce here the basic concepts of what a test case and write a simple
one. As a command do not use anything complicated (``true`` may be too
simple, but something easy like that, do not overwhelm the reader, here
he has to learn test cases, not linux).

Link back to previous to say how to include this in a test plan.

Outcome: Run the new test plan, show outcome, also create a failing one
and check that it does fail

Manual Test Case
----------------

Introduce here the basics of the purpose/idea of a manual test case.

Outcome: Run the test plan, show how the new test case is presented and
check that pass/fail is reported correctly

--------------

   From here onward, we introduce features and use them in a test
   case/plan, so that after each chapter it is clear what they do, how
   to use them and how to use what they produce in practice

Category
========

Outcome: Create a category, assign it to a test case

Resources
=========

Here mention what a resource is and name spacing, redirect to reference
for more.

Basic usage
-----------

Here introduce how resources are formatted and write a simple resource
job. This can be: is a file there?

Now write a test that uses this resource (command true?), show that it
passes, remove the file, show that the job is skipped, introduce here
``fail-on-resource``. Show that it fails.

Outcome: Test job that uses resources, understands how to create simple
ones and use them

Combining resources
-------------------

Here create a second resource job, this can be is another file present?

Now write a test that uses one, one that uses the other and one that
uses both (``and``/``or``). Show how they are skipped or run for the
given resource evaluation results.

   Consider pointing to the complexity note in the reference here

Ourcome: Two resource jobs, three tests, knowledge on how resource
expressions work.

Manifest
========

Introduce what a manifest entity is and recall where the disk cache is
stored.

Here we should only explain how to define a manifest and introduce the
basic kws (point to reference for more), then create a test plan that
uses one of the manifest entities that we just defined and run it,
filling the manifest as prompted.

Mention here the job to show all manifest entities

Outcome: Test that uses a manifest entity, knowledge on where the
manifest is store/how to read it

Templates
=========

Here introduce templates, point to reference for more.

Basic Template
--------------

The basic example
`here <https://canonical-checkbox.readthedocs-hosted.com/en/stable/reference/units/template.html#basic-example>`__
is pretty ok, I would simplify it a bit by removing one resource (3
echos) and the filtering (``requires``) as it is explained above. Also,
less text, more doing. Command should be just a plain ``echo`` so that
the user can familiarize with the template substitution

Outcome: Template that the user can try out and see the jobs that are
generated/run them and see a comprehensible output

Jinja Templates
---------------

Explain here how to use jinja templates (``template-engine: jinja2``),
and provide a basic usage. Create a template that generates a job using
at least one jinja feature, let the user run the generated test plan.

Outcome: Template that generates a test plan via jinja
