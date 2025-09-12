.. _adv_test_plan:

===================
Writing a test plan
===================

This tutorial will guide you in writing a test plan to test the Network
connection on your machine. We will do this by re-using tests that are already
available in the ``tutorial provider`` and that you got to write yourself in
the previous tutorial.

.. note::
  All of the commands in this tutorial are using the
  ``com.canonical.certification`` namespace. If you want to continue the one you
  have started before, remember to change the namespace
  (i.e. ``2024.com.tutorial::tutorial``) in the commands as well!

Inclusions
==========

When we want a test plan to contain a test, what we do in Checkbox is including
it. There are a few kinds of inclusions but they all have the same underlying
purpose: to tell Checkbox that we want to run something. Start by creating a
new test plan in the same provider we created in the previous tutorial.

.. note::

  We generally advise to keep test plans and test jobs in separate files, but
  this is not compulsory. You can find this definition in
  ``providers/tutorial/units/test-plan.pxu``

We now have a convenient container where to put all tests we previously
developed, let's include them in a new ``test plan``:

.. code-block:: none

  unit: test plan
  id: tutorial-extended
  _name: Extended Tutorial Test Plan
  include:
    network_available
    network_speed

To run the test plan we can use ``run`` as we previously did for individual
tests:

.. code-block:: none

   (checkbox_venv) $ checkbox-cli run com.canonical.certification::tutorial-extended
   [...]
   ==================================[ Results ]===================================
   ☑ : Fetches information of all network interfaces
   ☑ : Test that the internet is reachable
   ☑ : Test that the network speed is acceptable

.. important::
   Remember to run ``python3 manage.py validate`` before trying your changes.
   You will catch many mistakes that way.

Note how, as we previously saw, Checkbox automatically pulled the resource
job needed. This operation, as we previously mentioned, is not the safe way to go
about dependency management, it is just an aid Checkbox gives you while
developing. Jobs that are automatically pulled are placed in a random spot in
the list where you may already have broken the thing you are trying to fetch
info about!
With that being said, let's fix it before we forget:

.. code-block:: none

  unit: test plan
  id: tutorial-extended
  _name: Extended Tutorial Test Plan
  include:
    network_iface_info
    network_available
    network_speed

Given the brevity of our Test Plan, we are able to reason about it by opening
the definition but what if we want to inspect a more complicated one or do some
more advanced querying? That is where ``expand`` comes to our rescue.

Run the following and see the result:

.. code-block:: none

   (checkbox_venv) $ checkbox-cli expand -f json com.canonical.certification::tutorial-extended  | jq

   [
     {
       "_summary": "Test that the internet is reachable",
       "certification-status": "non-blocker",
       "command": " ping -c 1 1.1.1.1",
       "flags": "simple",
       "id": "com.canonical.certification::network_available",
       "requires": " (network_iface_info.link_info_kind == \"\" and network_iface_info.link_type == \"ether\")",
       "unit": "job"
     },
     {
       "_summary": "Fetches information of all network interfaces",
       "certification-status": "non-blocker",
       "command": " ip -details -json link show | jq -r '\n     .[] | \"interface: \" + .ifname +\n     \"\\nlink_info_kind: \" + .linkinfo.info_kind +\n     \"\\nlink_type: \" + .link_type +\n     \"\\noperstate: \" + .operstate + \"\\n\"'",
       "id": "com.canonical.certification::network_iface_info",
       "plugin": "resource",
       "unit": "job"
     },
     {
       "_summary": "Test that the network speed is acceptable",
       "certification-status": "non-blocker",
       "command": " curl -Y 600 -o /dev/null \\\n   https://cdimage.ubuntu.com/ubuntu-mini-iso/noble/daily-live/current/",
       "depends": "network_available",
       "flags": "simple",
       "id": "com.canonical.certification::network_speed",
       "unit": "job"
     }
  ]

Status overrides
================

The certification status of a job can be defined in its definition. This is
useful, but limiting, as one may want the same test to be a certification
blocker in one test plan while not in another. Checkbox supports overrides in
test plans that allow you to change the certification status (common) or the
category (uncommon) of a job in that specific test plan.

Going back to the test plan we just defined let's add the following and see the
effect in the ``expand`` output:

.. code-block:: none

  unit: test plan
  id: tutorial-extended
  _name: Extended Tutorial Test Plan
  include:
    network_iface_info
    network_available
    network_speed certification-status=blocker
  certification_status_overrides:
    apply blocker to network_available


Running ``expand`` we can see that the certification status changed:

.. code-block:: none


  (checkbox_venv) $ checkbox-cli expand -f json com.canonical.certification::tutorial-extended  | jq 'map({id: .id, "certification-status": .["certification-status"]})'
  [
    {
      "id": "com.canonical.certification::network_available",
      "certification-status": "blocker"
    },
    {
      "id": "com.canonical.certification::network_iface_info",
      "certification-status": "non-blocker"
    },
    {
      "id": "com.canonical.certification::network_speed",
      "certification-status": "blocker"
    }
  ]

Note that there are two ways of setting overrides. You should always prefer
the inline override over the other if possible. The block override
(``certification_status_overrides``) is meant to be used only when you want to
use a regex to apply the override (to match a subset of a template expansion)
or when the job you want to override is not in the list due to ``nested-parts``
(that we will introduce further below).

Bootstrap Inclusions
====================

As we have previously discussed, resources are the backbone of Checkbox
information gathering. Using the data they generate, jobs are skipped or ran and
templates are instantiated. Although Checkbox does try to pull all resources
and dependencies you may need into a test plan automatically, jobs may
interfere or break resources so, ideally, we would like to run them before
anything else. Bootstrap include does exactly this.

The bootstrap section of a test plan is the initial information gathering phase
of a test plan. Although there aren't any limitations as to what you can include
in the ``bootstrap_include`` section, we advise to only put there information
gathering jobs.

Let's go back to our test plan and move the resource job ``network_iface_info``
in the ``bootstrap_include`` section:

.. code-block:: none

  unit: test plan
  id: tutorial-extended
  _name: Extended Tutorial Test Plan
  bootstrap_include:
    network_iface_info
  include:
    network_available
    network_speed certification-status=blocker
  certification_status_overrides:
    apply blocker to network_available

You may have noticed we weren't including ``network_available_interface`` in
the test plan before, this is because it would not have expanded
deterministically. One of the dangers of letting Checkbox
automatically pull resource jobs for you is that, in some situations, like
``template-resource``, it won't do it. If you were to remove the test that
actually pulled the resource automatically (the one that uses it as in the
``resource`` field), you would inadvertently lose test coverage.

Let's update the test plan including it:

.. code-block:: none

  unit: test plan
  id: tutorial-extended
  _name: Extended Tutorial Test Plan
  bootstrap_include:
    network_iface_info
  include:
    network_available_interface
    network_available
    network_speed certification-status=blocker
  certification_status_overrides:
    apply blocker to network_available

When we run ``expand`` on the test plan, two important changes occur in the
output:

- First, the resource job is no longer visible – this is expected! The
  bootstrap section of a test plan is meant to gather essential data before the
  main test execution but is not composed of actual tests, so the jobs there
  are excluded from the expand command.
- Second, our newly added template wasn't expanded. This happens because a
  template is expanded on the result of a resource, and only running the
  resource can give that output (that is often specific to one machine!). If we
  want to see all the jobs that would be executed on the current machine if we
  ran that test plan, we can use ``list-bootstrapped``:

.. code-block:: none

  # Note: your output will be slightly different, depending on how many ifaces you have!
  (checkbox_venv) $ checkbox-cli list-bootstrapped com.canonical.certification::tutorial-extended
  com.canonical.certification::network_iface_info
  com.canonical.certification::network_available_enp2s0f0
  com.canonical.certification::network_available_enp5s0
  com.canonical.certification::network_available_wlan0
  com.canonical.certification::network_available_enp7s0f3u1u2
  com.canonical.certification::network_available
  com.canonical.certification::network_speed


Nested parts
============

It is often useful to re-use the same test plan to test a functionality. This
is for many reasons but mainly the fact that test plans are always evolving,
adding better tests, increasing the coverage, removing old ones, and to keep
them in sync is a very error prone chore. Checkbox has a feature to help with
this: ``nested_part``.

When a test plan has a ``nested_part``, all "parts" (jobs + other nested parts)
are added to the test plan. Let's try this with an example. When a new test plan
is being developed for certification purposes, one nested part is compulsory to
include (or the submissions will be rejected): ``submission-cert-automated``.
Let's include it in our test plan:

.. code-block:: none
  :emphasize-lines: 10-12

  unit: test plan
  id: tutorial-extended
  _name: Extended Tutorial Test Plan
  bootstrap_include:
    network_iface_info
  include:
    network_available_interface
    network_available
    network_speed certification-status=blocker
  nested_part:
    com.canonical.certification::submission-cert-automated
  certification_status_overrides:
    apply blocker to network_available

.. note::
   In your provider, you have to specify the full namespace to get access to
   ``submission-cert-automated``. Also, if you didn't install it before, you
   have to install the base provider, as there is where this test plan is
   defined. As you did for your, run ``python3 manage.py develop`` while having
   the virtual env active.

Another very useful thing you can do with nested parts is to create aliases.
For example, if you were to rename a test plan in a provider that is used by
others, it may be useful for everyone if you provide a backward compatible
alias for some time, so that they can adjust to the change. Say for example we
started publishing our tutorial test plan giving it the id
``tutorial-extended-oldid``. This is how we would create the backward
compatible alias:

.. code-block:: none

  unit: test plan
  id: tutorial-extended-oldid
  _name: (alias) Extended Tutorial Test Plan (Changed id to: `tutorial-extended`)
  nested_part:
    tutorial-extended
  include:

.. note::
  Notice how we also changed the ``_name`` so that it points to the "new" id.
  This makes the migration from the old id (now an alias) to the new one way
  easier and frictionless. Also note that include is mandatory, so you have to
  place it there empty.


Exclusions
==========

Nested parts are useful, they reduce code duplication allowing us to inherit
inclusions (and nested parts!) from other test plans. A common issue with this
is that we may not want to introduce all tests in a test plan, but just most of
them. If this is the case then ``exclusions`` are the way to go.

For example, the ``network_speed`` test that we have in our test plan may be
expensive to run, we can create a new test plan with it excluded as follows:

.. code-block:: none

  unit: test plan
  id: tutorial-extended-no-speed
  _name: Extended Tutorial Test Plan without the speed test
  nested_part:
    tutorial-extended
  exclude:
    network_speed
  include:

Now if we ``list-bootstrapped`` the test plan we will see that the test is
missing:

.. code-block:: none

  (checkbox_venv) $ checkbox-cli list-bootstrapped com.canonical.certification::tutorial-extended-no-speed
  [...jobs from submission-cert-automated...]
  com.canonical.certification::network_iface_info
  com.canonical.certification::network_available_enp2s0f0
  com.canonical.certification::network_available_enp5s0
  com.canonical.certification::network_available_wlan0
  com.canonical.certification::network_available_enp7s0f3u1u2
  com.canonical.certification::network_available

.. note::
   Excluding a test via ``exclude`` in the test plan is different from using
   ``exclude`` in the launcher. If you use ``exclude`` in the launcher, you
   are modifying the test plan, so it will not be accepted as a submission on
   C3, whereas if you use ``exclude`` in a test plan, you are creating a new,
   different test plan.

Using exclude to remove tests is one mechanism to customize your test plan, but
be warned, if you find yourself adding many excludes (10+), you should probably
re-evaluate the nested parts you are choosing for your test plan or reason
about why you are excluding those tests, maybe some need an updated definition!

.. warning::
   While ``exclude`` is a list of regexes, so you can use a regex to exclude
   jobs, you should most likely avoid doing that as you may inadvertently deselect
   more jobs than you were aiming for. Try to always precisely match
   what you want to exclude, for templates, for example, use the template id
   whenever you can instead of regex matching the generated id.

Mandatory inclusions
====================

Exclusions are a nice mechanism to inherit a test plan partially, but they are
sometimes too powerful. One may exclude things by mistake and completely void a
test plan of any use, for example excluding all functional tests from it.
Mandatory inclusions are a tool to avoid this. When a test is mandatory
included, it is not affected by exclude.

To get an example, let's go back to our new test plan and try to exclude the
``info/systemd-analyze-critical-chain`` test:

.. code-block:: none

  unit: test plan
  id: tutorial-extended-no-speed
  _name: Extended Tutorial Test Plan without the speed test
  nested_part:
    tutorial-extended
  exclude:
    network_speed
    info/systemd-analyze-critical-chain

See how the output of ``list-bootstrapped`` is unaffected.

.. code-block:: none

  (checkbox_venv) $ checkbox-cli list-bootstrapped com.canonical.certification::tutorial-extended-no-speed
  [...]
  com.canonical.certification::info/systemd-analyze-critical-chain
  [...]

The reason is that all tests in the ``submission-cert-automated`` nested part are mandatory
includes: they will be executed regardless of any other rule in your test plan.
