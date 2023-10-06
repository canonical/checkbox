.. _base_tutorial_launcher:

=========
Launchers
=========

Checkbox features and behaviors can be configured and customized using
a launcher.

In this section, you will use a launcher to filter the list of test plans
displayed when running Checkbox, pre-select a test plan, automatically execute
a test plan without manual interaction and configure the environment variables
used by some of the test cases. Finally, you will tailor the output generated
by Checkbox to your needs.

Filter the list of test plans
=============================

When you ran Checkbox in the previous section, you were probably overwhelmed
with the number of test plans available. Using a launcher, it is possible to
filter them to only select the ones that matter to you.

Create a file named ``mylauncher`` and add the following information in it:

.. code-block:: none
    :caption: mylauncher
    :name: initial-launcher

    [launcher]
    launcher_version = 1

    [test plan]
    filter = *tutorial*

Save it, then launch Checkbox using this launcher:

.. code-block:: none

    $ checkbox.checkbox-cli launcher mylauncher

The test plan selection screen should be much less intimidating now!

Let's review the content of this launcher.

The ``[launcher]`` section contains meta-data related to the launcher itself.
``launcher_version`` is set to ``1`` as it is the version of the launcher
syntax currently in use.

In the ``[test plan]`` section, we set the ``filter`` to ``*tutorial*``. By
doing so, the only test plans that will be displayed are the one whose
``id`` contain the word ``tutorial``. Note the use of the ``*`` `glob pattern
<https://en.wikipedia.org/wiki/Glob_(programming)>`_, similar to Bash for
instance.

Try replacing ``*tutorial*`` with ``*wireless*`` and see how it affects the
list of test plans displayed in Checkbox.

Select a test plan by default
=============================

Set the filter back to ``*tutorial*`` in the ``[test plan]`` section and add
the following line:

.. code-block:: none
    :caption: mylauncher
    :name: launcher-filter
    :emphasize-lines: 7

    [launcher]
    launcher_version = 1
    app_id = com.canonical.certification:tutorial

    [test plan]
    filter = *tutorial*
    unit = com.canonical.certification::tutorial-base

Start Checkbox using the launcher. In addition to filtering the list of test
plans, the "Checkbox Base Tutorial" test plan is now selected by default.
You just need to press ``Enter`` to go to the test selection screen.

Bypass test plan and test selection screens
===========================================

Now, let's say that when you run Checkbox, you always want to select the
same test plan, and you always want to run all the tests in it. You don't
want to spend time in the test plan selection screen nor the test selection
screen. Modify your launcher so it looks like that:

.. code-block:: none
    :caption: mylauncher
    :name: launcher-forced-selection
    :emphasize-lines: 7-10

    [launcher]
    launcher_version = 1
    app_id = com.canonical.certification:tutorial

    [test plan]
    unit = com.canonical.certification::tutorial-base
    forced = yes

    [test selection]
    forced = yes

Run Checkbox with this modified version of the launcher:

.. code-block:: none

    $ checkbox.checkbox-cli launcher mylauncher

Notice how none of the initial screens are shown and Checkbox immediately
runs the "Checkbox Base Tutorial" test plan. This is because:

- in the ``[test plan]`` section, we selected a test plan with ``unit =
  com.canonical.certification::tutorial-base`` and we forced its use with
  ``forced = yes``, bypassing the test plan selection screen;
- in the ``[test selection]`` section, we forced the selection of all the
  tests, bypassing the test selection screen.

Customize test cases with environment variables
===============================================

One of the test cases in the Tutorial test plan uses the value set in an
environment variable. Add the following lines in the launcher:

.. code-block:: none
    :caption: mylauncher
    :name: launcher-environment
    :emphasize-lines: 12-13

    [launcher]
    launcher_version = 1
    app_id = com.canonical.certification:tutorial

    [test plan]
    unit = com.canonical.certification::tutorial-base
    forced = yes

    [test selection]
    forced = yes

    [environment]
    TUTORIAL = Value from my launcher!

Run Checkbox using your launcher, and observe the output of the
``tutorial/environment_variable`` test case. The output now shows ``Value
from my launcher!``.

The ``[environment]`` section is often used to provide customized values to
test cases. For instance, you may have a generic test case to connect to a
WiFi access point, but its SSID and password might change, so you can use an
environment variable in the test case definition and set their values in the
``[environment]`` section of your launcher.

Tailor Checkbox output
======================

At the end of the test session, Checkbox summarizes the test results on
the screen, generates test reports and test archive, and asks you whether
you want to upload the test results to the Canonical :term:`Certification
website`. Let's say you don't need to upload the results there; you are only
interested in the text summary and the test reports.

Edit the launcher file:

.. code-block:: none
    :caption: mylauncher
    :name: launcher-stock-reports
    :emphasize-lines: 4

    [launcher]
    launcher_version = 1
    app_id = com.canonical.certification:tutorial
    stock_reports = text, submission_files

    [test plan]
    unit = com.canonical.certification::tutorial-base
    forced = yes

    [test selection]
    forced = yes

    [environment]
    TUTORIAL = Value from my launcher!

Run Checkbox using this launcher and observe that once the test plan is
finished running, Checkbox generates a summary on the screen and provides
the links to the test reports and test archive, but does not ask if the
result should be uploaded to the Canonical Certification website.

This is thanks to the customization of the ``stock_reports`` field in the
``[launcher]`` section. If not specified in the launcher, its default value
is set to ``text, certification, submission_files``.

In Checkbox language, submissions files are the HTML test report as well as
an archive containing the test results and additional logs that might have
been produced by the test cases.

A note about config files
=========================

So far, you have customized Checkbox using a launcher file. It is also
possible to put these options in a configuration file that Checkbox will use
when it is launched. The main difference is that you don't have to specify
the launcher when running Checkbox.

Create the file ``~/.config/checkbox.conf`` and add the following content
in it:

.. code-block:: none

    [launcher]
    launcher_version = 1
    app_id = com.canonical.certification:tutorial
    stock_reports = text, submission_files

    [test plan]
    unit = com.canonical.certification::TODO
    forced = yes

    [test selection]
    forced = yes

    [environment]
    TUTO = tutorial

Now, run Checkbox without any argument:

.. code-block:: none

    $ checkbox.checkbox-cli

You should see that Checkbox behaves exactly the same as in the previous
section. It found the configuration from the ``~/.config/checkbox.conf``
file and used it to automatically select the test plan and run it.

Configuration files can be placed elsewhere on the system, and Checkbox
will follow a certain resolution order to decide what configuration to
use if more than one configuration files define the same key. Please check
:ref:`checkbox_configs` for more information.

Checkbox comes with a handy command to check what configuration is being used,
and where it comes from. Run the following command:

.. code-block:: none

   $ checkbox.checkbox-cli check-config
   Configuration files:
     - /var/snap/checkbox/2799/checkbox.conf
     - /home/user/.config/checkbox.conf
       [config]
         config_filename=checkbox.conf      (Default)
       [launcher]
         app_id=com.canonical.certification:tutorial From config file: /home/user/.config/checkbox.conf
         app_version=                       (Default)
         launcher_version=1                 From config file: /home/user/.config/checkbox.conf
         local_submission=True              (Default)
         session_desc=                      (Default)
         session_title=session title        (Default)
         stock_reports=text, submission_files From config file: /home/user/.config/checkbox.conf
       [test plan]
         filter=*                           (Default)
         forced=True                        From config file: /home/user/.config/checkbox.conf
         unit=com.canonical.certification::TODO From config file: /home/user/.config/checkbox.conf
       [test selection]
         exclude=                           (Default)
         forced=True                        From config file: /home/user/.config/checkbox.conf
       (...)
       [environment]
         STRESS_S3_WAIT_DELAY=120           From config file: /var/snap/checkbox/2799/checkbox.conf
       (...)
         TUTO=tutorial                      From config file: /home/user/.config/checkbox.conf
       (...)
    No problems with config(s) found!

You can see:

- a list of the configuration files being used
- for each section, the configured parameters being used
- the origin of each of these customized parameters
- an overall status report ("No problems with config(s) found!")

This can be really helpful when debugging a Checkbox run. For instance,
looking at the output above, I can see that the ``STRESS_S3_WAIT_DELAY``
environment variable is set to ``120`` because it is specified in
a Checkbox configuration that comes with the snap version I'm using
(``/var/snap/checkbox/2799/checkbox.conf``).

If you want to debug a Checkbox run that involves a ``launcher``, fear not.
The ``check-config`` command works with launchers as well. Try the previous
command with the ``launcher`` we created before:

.. code-block:: none
    :emphasize-lines: 8,14,17-18,21,28

    $ checkbox.checkbox-cli check-config mylauncher
    Configuration files:
     - /var/snap/checkbox/2799/checkbox.conf
     - /home/user/.config/checkbox.conf
       [config]
         config_filename=checkbox.conf      (Default)
       [launcher]
         app_id=com.canonical.certification:tutorial From config file: /home/user/mylauncher
         app_version=                       (Default)
         launcher_version=1                 From config file: /home/user/.config/checkbox.conf
         local_submission=True              (Default)
         session_desc=                      (Default)
         session_title=session title        (Default)
         stock_reports=text, submission_files From config file: /home/user/mylauncher
       [test plan]
         filter=*                           (Default)
         forced=True                        From config file: /home/user/mylauncher
         unit=com.canonical.certification::tutorial-base From config file: /home/user/mylauncher
       [test selection]
         exclude=                           (Default)
         forced=True                        From config file: /home/user/mylauncher
       (...)
       [environment]
         STRESS_S3_WAIT_DELAY=120           From config file: /var/snap/checkbox/2799/checkbox.conf
       (...)
         TUTO=tutorial                      From config file: /home/user/.config/checkbox.conf
       (...)
         TUTORIAL=Value from my launcher!   From config file: /home/user/mylauncher
    No problems with config(s) found!

Create an executable launcher
=============================

So far, we have called our launcher using the ``launcher`` option of the
``checkbox-cli`` tool. It is however possible to turn our launcher into a
file that can be interpreted, similarly to an executable bash script.

At the top of the launcher file, add this line:

.. code-block:: none
    :caption: mylauncher
    :name: launcher-shebang
    :emphasize-lines: 1

    #!/usr/bin/env checkbox.checkbox-cli

    [launcher]
    launcher_version = 1
    app_id = com.canonical.certification:tutorial
    stock_reports = text, submission_files

    [test plan]
    unit = com.canonical.certification::tutorial-base
    forced = yes

    [test selection]
    forced = yes

    [environment]
    TUTORIAL = Value from my launcher!

Make the launcher executable:

.. code-block:: none

    $ chmod +x mylauncher

Run it:

.. code-block:: none

    $ ./mylauncher

Checkbox runs exactly like before! The line we added is called a `shebang
<https://en.wikipedia.org/wiki/Shebang_(Unix)>`_ and allows us to run
``checkbox.checkbox-cli`` using the configuration provided.

Wrapping up
===========

In this section, you've got more familiar with Checkbox launchers. You created
a launcher that modified the behavior of Checkbox by pre-selecting a test
plan and executing it, provided environment variables to the test cases and
outputted only what you needed: a text summary and the submission files.

There are many more options available in the launchers to customize
Checkbox runs. Please check the :ref:`launchers reference<launcher>` for
more information.
