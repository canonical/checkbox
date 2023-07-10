.. _tutorials:

=============
Core Tutorial
=============

   This uses a new tutorial TP, its a small addition but could make a
   huge difference, we can custom tailor a new user experience with it.
   It will be referenced as tutorial-plan

..

   This uses explain and introduce interchangeably, by explain I don’t
   mean a 300 pages novella about the feature but a dry simple
   explanation of its purpose and how to use it # Introduction Here
   mention what checkbox is

Installing checkbox
-------------------

Here we introduce snaps and debs for checkbox, introduce here the
concept of ``core`` and ``frontend``.

Outcome: checkbox.checkbox-cli or checkbox-cli starting

Running First Test Plan
-----------------------

Here we can explain a little bit the different kind of jobs that we have
while we encounter them in the execution, explain comments and outcomes.

Running a job will also ask if you want to submit it, it may be worth
explaining what that means! Also: outcome is saved, point to where and
how

Outcome: tutorial-plan results

Using basic launcher
--------------------

~ ``checkbox-cli launcher.conf`` Outcome: Auto-starting tutorial-plan
test, Filtered test list

Using basic configuration
-------------------------

Explain how configs are used, **where to put them** Outcome:
Auto-starting tutorial-plan test via conf, filtered test list, also:
``check-config`` usage for config validation/see what is going on

Machine Manifest
----------------

Explain how the machine manifest works/is created and where it is.
Create one with the create manifest job, now re launch and edit it. Edit
it via text editor.

Using them all
--------------

Here explain how conf/MM/launcher are prioritized between them (launcher
wins) and make the user do a couple of examples like setting start.

Recall here ``check-config``, and show how it tracks the origin of
values

Outcomes: Auto starting tutorial-plan via conf and launcher,
``check-config`` source explained

Remote testing
==============

Here say a couple of words on the motivation of remote testing, say that
if run with no args, checkbox-cli is local (and deprecated? useful to
check local configs? idk)

Basic
-----

Explicitly start two ends, one per terminal, to play around with them.

Outcome: Two terminals, one running agent, one running controller,
tutorial-plan tests run “remotely”

Configuration
-------------

Explicitly explain how configuration interact with agent/controller,
with examples go through who reads what how, recall ``check-config`` and
show it works remotely

Outcome: A couple of combination of configurations with examples,
running tests remotely with filters etc.

Test Output
===========

Here guide the user through an output, use the tutorial plan output.

Outcome: Understanding of the main, most common fields of the output

   Once here, the reader of the tutorial should have a good knowledge of
   the basics of checkbox, he should be able to run tests, comprehend
   the output and see/modify/debug the configuration

Advanced Configs
================

Here explain every feature of config files, recall ``check-config``
somewhere so that if someone skims through the guide it is known.

This page is a pretty good beginning:
https://canonical-checkbox.readthedocs-hosted.com/en/stable/reference/launcher.html

The only thing to change is to prune uncommon config values and
explanation and have an actionable config, per section, that the user
can load and “experience”.
