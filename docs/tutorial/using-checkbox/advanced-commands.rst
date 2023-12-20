.. _base_tutorial_commands:

============================
A few more Checkbox commands
============================

Checkbox comes with a bunch of commands. To see them, run the following in
a terminal:

.. code-block:: none

    checkbox.checkbox-cli --help

    usage: checkbox-cli [-h] [-v] [--debug] [--clear-cache] [--clear-old-sessions] [--version]
                        {check-config,launcher,list,run,startprovider,submit,show,
                         list-bootstrapped,merge-reports,merge-submissions,tp-export,
                         service,remote}

    positional arguments:
      {check-config,launcher,list,run,startprovider,submit,show,list-bootstrapped,
       merge-reports,merge-submissions,tp-export,service,remote}
                            subcommand to run

    options:
      -h, --help            show this help message and exit
      -v, --verbose         print more logging from checkbox
      --debug               print debug messages from checkbox
      --clear-cache         remove cached results from the system
      --clear-old-sessions  remove previous sessions' data
      --version             show program's version information and exit

You've already seen the ``check-config`` and the ``launcher`` commands. In
this section, you will use a few other commands that can be helpful to
explore what's available in Checkbox.

List available objects
======================

Checkbox handles a lot of "objects" when it's running. These objects can be the
different Checkbox unit types (:ref:`jobs<job>`, :ref:`test plans<test-plan>`,
etc.), but they also include the test scripts, the test providers themselves
and even the test sessions known to Checkbox!

To get a list of all the available Checkbox objects on your system, run:

.. code-block:: none

    checkbox.checkbox-cli list
    service 'service object'
      children
        provider 'com.canonical.plainbox:manifest'
          children
            file '/snap/checkbox22/current/lib/python3.10/site-packages/plainbox/impl/providers/manifest/README.md'
            file '/snap/checkbox22/current/lib/python3.10/site-packages/plainbox/impl/providers/manifest/bin/plainbox-manifest-collect'
    (...)
            job 'com.canonical.certification::tpm2.0_4.1.1/tpm2_verifysignature'
            job 'com.canonical.certification::tpm2.0_4.1.1/pcr0_mismatch_check'
            job 'com.canonical.certification::tpm2.0_4.1.1/context_gap_max_check'
            file '/snap/checkbox22/current/providers/checkbox-provider-tpm2/units/tpm2_4.1.1.pxu'

That's **a lot** of objects! Fortunately, it is possible to retrieve objects
from a specific group. Let's see what test plans are available, for instance:

.. code-block:: none

    checkbox.checkbox-cli list "test plan"

    test plan 'com.canonical.certification::6lowpan-automated'
    test plan 'com.canonical.certification::acpi-automated'
    test plan 'com.canonical.certification::audio-cert-full'
    (...)
    test plan 'com.canonical.certification::tpm-cert-focal-automated'
    test plan 'com.canonical.certification::tpm-cert-automated'

Combined with a ``grep`` command, it is possible to find all the test plans
related to audio testing:

.. code-block:: none

    checkbox.checkbox-cli list "test plan" | grep audio

    test plan 'com.canonical.certification::audio-cert-full'
    test plan 'com.canonical.certification::audio-cert-manual'
    (...)
    test plan 'com.canonical.certification::after-suspend-audio-pa-manual'
    test plan 'com.canonical.certification::after-suspend-audio-automated'

Or let's list all the available jobs (test cases):

.. code-block:: none

    checkbox.checkbox-cli list all-jobs
    
    id: com.canonical.certification::6lowpan/kconfig
    kernel config options for 6LoWPAN
    id: com.canonical.certification::IEEE_80211
    Creates resource info for wifi supported protocols/interfaces
    id: com.canonical.certification::acpi/oem_osi
    test ACPI OEM _OSI strings
    (...)

By default, the output for the ``all-jobs`` option is to list the job
identifier followed by its summary (or ``<missing summary>`` if there is no
summary). We can tailor the output using the ``--format`` parameter and all the
fields available from the jobs. To see what fields are available, run:

.. code-block:: none

    checkbox.checkbox-cli list all-jobs --format ?
    
    Available fields are:
    _description, _purpose, _siblings, _steps, _summary, _verification, after,
    category_id, command, depends, environ, estimated_duration, flags, full_id,
    id, imports, plugin, require, requires, template-engine, template-filter,
    template-resource, template-unit, unit, user

.. note::

    These fields are explained in the :ref:`job` page.

.. note::

    The underscore before some of the fields names simply means the content
    of this field can be translated into another language.

To create a table listing each job id and their summary, run:

.. code-block:: none

    checkbox.checkbox-cli list all-jobs --format "{id:30}\t|\t{_summary}\n"

    6lowpan/kconfig               	|	kernel config options for 6LoWPAN
    IEEE_80211                    	|	Creates resource info for wifi supported protocols/interfaces
    acpi/oem_osi                  	|	test ACPI OEM _OSI strings
    acpi_sleep_attachment         	|	<missing _summary>
    (...)
    xinput                        	|	Creates resource info from xinput output.
    zapper_capabilities           	|	Get Zapper's setup capabilities
    collect-manifest              	|	Collect the hardware manifest (interactively)
    manifest                      	|	Hardware Manifest

.. note::

    ``\n`` and ``\t`` in the formatting string are interpreted and replaced
    with new line and tab respectively.

    When using your own formatting, the jobs are not suffixed with a new line:
    you have to explicitly use it.

List the content of a test plan as executed by Checkbox
=======================================================

In the previous section, you've listed all the test
plans related to audio. Select one of them, for instance
``com.canonical.certification::audio-cert-automated``, and see what jobs
it contains:

.. code-block:: none

    checkbox.checkbox-cli list-bootstrapped com.canonical.certification::audio-cert-automated

    com.canonical.plainbox::manifest
    com.canonical.certification::package
    com.canonical.certification::audio/detect_sinks
    com.canonical.certification::device
    com.canonical.certification::audio/detect_sources
    com.canonical.certification::audio/alsa_record_playback_automated
    com.canonical.certification::audio/alsa_info_collect
    com.canonical.certification::audio/alsa_info_attachment
    com.canonical.certification::audio/list_devices
    com.canonical.certification::audio/valid-sof-firmware-sig

If you were to run this test plan with Checkbox, it would run these jobs in
the order shown above.

.. note::

    The name of this command refers to the Checkbox :term:`bootstrapping`
    phase.

But what are these jobs exactly? You can use the ``show`` command to see the
content of a Checkbox object.

Show the content of a Checkbox object
=====================================

Have a look at the ``com.canonical.certification::audio/list_devices`` job
listed in the ``com.canonical.certification::audio-cert-automated`` test
plan above, for instance. What is it exactly? What does it contain? What is
its **definition?** Use the ``show`` command to find out:

.. code-block:: none

    checkbox.checkbox-cli show com.canonical.certification::audio/list_devices

    origin: /snap/checkbox22/current/providers/checkbox-provider-base/units/audio/jobs.pxu:1-9
    plugin: shell
    category_id: com.canonical.plainbox::audio
    id: audio/list_devices
    estimated_duration: 1.0
    requires:
     device.category == 'AUDIO'
     package.name == 'alsa-base'
    command: cat /proc/asound/cards
    _description: Test to detect audio devices

The first line tells you that this job comes from lines 1 to 9 of the
``/snap/checkbox22/current/providers/checkbox-provider-base/units/audio/jobs.pxu``
file. The other lines show its definition. We can see what it does ("Test to
detect audio devices"), how (using the ``cat /proc/asound/cards`` command),
and many other details.

.. note::

    Each of the fields shown in a job definition are explained in the
    :ref:`job` page.

Now that you know the definition of this job, you can run it to see what
the output generated by Checkbox look like.

.. _run_subcmd:

Run a particular test plan or a set of jobs
===========================================

Run the following command:

.. code-block:: none

    checkbox.checkbox-cli run ".*audio/list_devices"

    ===========================[ Running Selected Jobs ]============================
    ==============[ Running job 1 / 3. Estimated time left: 0:00:03 ]===============
    -----------[ Collect information about installed software packages ]------------
    ID: com.canonical.certification::package
    Category: com.canonical.plainbox::uncategorised
    ... 8< -------------------------------------------------------------------------
    name: accountsservice
    version: 22.07.5-2ubuntu1.4

    (...)

    ==============[ Running job 3 / 3. Estimated time left: 0:00:01 ]===============
    -----------------------------[ audio/list_devices ]-----------------------------
    ID: com.canonical.certification::audio/list_devices
    Category: com.canonical.plainbox::audio
    ... 8< -------------------------------------------------------------------------
     0 [PCH            ]: HDA-Intel - HDA Intel PCH
                          HDA Intel PCH at 0xf7f10000 irq 31
     1 [H340           ]: USB-Audio - Logi USB Headset H340
                          Logitech Inc. Logi USB Headset H340 at usb-0000:00:14.0-1, full speed
     2 [HDMI           ]: HDA-Intel - HDA ATI HDMI
                          HDA ATI HDMI at 0xf7e60000 irq 32
     3 [U0x46d0x802    ]: USB-Audio - USB Device 0x46d:0x802
                          USB Device 0x46d:0x802 at usb-0000:00:14.0-4, high speed
    ------------------------------------------------------------------------- >8 ---
    Outcome: job passed
    Finalising session that hasn't been submitted anywhere: checkbox-run-2023-07-24T09.01.24
    ==================================[ Results ]===================================
     ☑ : Collect information about installed software packages
     ☑ : Collect information about hardware devices (udev)
     ☑ : audio/list_devices

A few things to notice:

- Checkbox has executed the ``com.canonical.certification::audio/list_devices``
  job. Because it understands regular expression patterns, you were able to
  pass it ``.*audio/list_devices`` instead of the full job id.
- The output is quite similar to running Checkbox manually, except only a text
  summary is generated at the end (no submission files, no request to upload
  results to the Certification website).
- Although you asked Checkbox to run one job, it actually ran three. This is
  because the ``audio/list_devices`` job definition has some requirements from
  other jobs (namely, ``com.canonical.certification::packages`` and
  ``com.canonical.certification::device``), so these jobs are executed as well
  when you run it.

You can execute a set of jobs by using an appropriate regular expression. For
instance, ``checkbox.checkbox-cli run .*audio/.*`` would run every job whose
``id`` contain the string ``audio/`` (as well as the jobs they depend on).

.. warning::

    Be careful when using the ``run`` command with such open regular
    expressions because you might end up running quite a lot of jobs!

You can also run a whole test plan using the ``run`` command:

.. code-block:: none

    checkbox.checkbox-cli run com.canonical.certification::tutorial-base

This will run the Checkbox Base Tutorial test plan, executing all the jobs in
it and providing a text summary of the test run.

Wrapping up
===========

Congratulations! You've completed the Checkbox usage tutorial!

You've installed Checkbox, run a test plan and reviewed the report generated,
written a launcher to customise a test run, discovered how to run Checkbox on
one device to control another device, and used Checkbox commands to navigate
the available objects in Checkbox. You are now ready to use Checkbox to test
any kind of devices!

In the :ref:`advanced tutorial<TODO>`, you will learn how to write new tests
for Checkbox and how to create your own Checkbox-based snaps.
