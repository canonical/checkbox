.. _base_tutorial_manifest:

========
Manifest
========

Although Checkbox gathers information about the device being tested
automatically and can use this information to infer what kind of testing
can be done on the device, it is not always possible (nor desirable) to
depend only on automation. For instance, a device may have a WiFi chip,
but if it's not compatible with Ubuntu, this WiFi chip will not be exposed
to the system, so Checkbox will not see it and will skip any WiFi-related
tests without raising an error. For this kind of scenario, Checkbox can use
a manifest. A manifest is a file that describes what is available on the
device, and what is not. Checkbox can then make use of this information to
decide whether to run a job or to skip it.

In this section, we will interact with the manifest to get a better
understanding of how it works, where it is located, and how to edit it.

Adding manifest information
===========================

Start Checkbox:

.. code-block:: none

    $ checkbox.checkbox-cli

When the test plan selection screen appears, press ``f`` to filter the list,
type ``manifest`` and press ``Enter`` to validate. You should see a test plan
named ``Checkbox Base Tutorial Test Plan (using manifest)``. Select it by
highlighting it and pressing ``Space``, then press ``Enter`` to continue. In
the test selection screen, just leave everything selected and press ``T``.

You will now see the System Manifest screen:

.. code-block:: none

     System Manifest:
    ┌──────────────────────────────────────────────────────────────────────────────┐
    │ Does this machine have this piece of hardware?                               │
    │   Touchscreen                            ( ) Yes   ( ) No                    │
    │                                                                              │
    │                                                                              │
    │                                                                              │
    │                                                                              │
    │                                                                              │
    └──────────────────────────────────────────────────────────────────────────────┘
     Press (T) to start Testing                                      Shortcuts: y/n

This screen appears because one of the job in the test plan we selected
requires information from the manifest. In this case, Checkbox would like
to know if the device we are testing has a touch screen. You can jump
from ``Yes`` to ``No`` using the arrow keys and select one option with the
``Space`` key. You can also use the ``y`` and ``n`` keys to select the right
answer directly.

Let's pretend our device does indeed have a touch screen. Press ``y`` to
select ``Yes``, then press ``T`` to start testing.

The jobs in the test plan will be executed, the test session will wrap up and
Checkbox will ask if you want to upload your results. Select ``n`` and press
``Enter`` to finish.

Let's look at what happened by looking at the text on the screen. Towards
the top, we can see:

.. code-block:: none

    =========================[ Resume Incomplete Session ]==========================
    There are 0 incomplete sessions that might be resumed
    Preparing...
    Saving manifest to /var/tmp/checkbox-ng/machine-manifest.json

The manifest file is a JSON file that Checkbox stores at a specific
location. If this file does not exist, it is created. It is then updated
using the values chosen in the System Manifest screen.

A bit below, we see a ``Hardware Manifest`` job being executed:

.. code-block:: none
    :emphasize-lines: 11

    =========[ Running job 2 / 3. Estimated time left (at least): 0:00:02 ]=========
    -----------------------------[ Hardware Manifest ]------------------------------
    ID: com.canonical.plainbox::manifest
    Category: com.canonical.plainbox::uncategorised
    ... 8< -------------------------------------------------------------------------
    ns: com.canonical.certification
    name: checkbox-provider-base
    has_audio_playback: 
    (...)
    has_touchpad: 
    has_touchscreen: True
    (...)
    has_wlan_adapter: 
    has_wwan_module:
     
    (...)
    
    ------------------------------------------------------------------------- >8 ---
    Outcome: job passed

This job will collect the information from the manifest file so that it
can be used by Checkbox later for each :ref:`manifest_entry` defined in the
providers. We can see that ``has_touchscreen`` (the :ref:`id<Manifest Entry
id field>` of the manifest entry unit that represents whether or not this
device has a touch screen) is set to ``True`` because we selected it in the
System Manifest screen.

Finally, a job that uses this information, ``tutorial/manifest``, is executed:


.. code-block:: none

    =========[ Running job 3 / 3. Estimated time left (at least): 0:00:01 ]=========
    ---------------------------[ A job using a manifest ]---------------------------
    ID: com.canonical.certification::tutorial/manifest
    Category: com.canonical.certification::tutorial
    ... 8< -------------------------------------------------------------------------
    This test is executed because user said this device has a touchscreen.
    ------------------------------------------------------------------------- >8 ---
    Outcome: job passed

Modifying the manifest information within Checkbox
==================================================

Let's run the same test plan again, but this time we will pretend the device
has no touch screen.

- Launch Checkbox using ``checkbox.checkbox-cli``.
- Filter the test plans using the ``f`` shortcut and the ``manifest`` filter.
- Select the ``Checkbox Base Tutorial Test Plan (using manifest)`` test plan.
- In the test selection screen, leave all the jobs selected and press ``T``.
- In the System Manifest screen, note that Checkbox remembers our previous
  choice (``Touchscreen`` is set to ``Yes``). This is because it parsed the
  manifest file and found the information stored. Press ``n`` to select ``No``
  instead, and press ``T`` to start the test.

This time, The jobs re-run screen is shown because the job that uses this
manifest information has been skipped. Press ``F`` to finish the test run (you
can select ``n`` when Checkbox asks if you want to upload the test results).

You can see the ``has_touchscreen`` key from the Hardware Manifest job is
now set to ``False``:

.. code-block:: none
    :emphasize-lines: 11

    =========[ Running job 2 / 3. Estimated time left (at least): 0:00:02 ]=========
    -----------------------------[ Hardware Manifest ]------------------------------
    ID: com.canonical.plainbox::manifest
    Category: com.canonical.plainbox::uncategorised
    ... 8< -------------------------------------------------------------------------
    ns: com.canonical.certification
    name: checkbox-provider-base
    has_audio_playback: 
    (...)
    has_touchpad: 
    has_touchscreen: False
    (...)
    has_wlan_adapter: 
    has_wwan_module:
     
    (...)
    
    ------------------------------------------------------------------------- >8 ---
    Outcome: job passed

and as a result, the job that depends on it is skipped:

.. code-block:: none
    :emphasize-lines: 5-6

    ---------------------------[ A job using a manifest ]---------------------------
    ID: com.canonical.certification::tutorial/manifest
    Category: com.canonical.certification::tutorial
    Job cannot be started because:
     - resource expression "manifest.has_touchscreen == 'True'" evaluates to false
    Outcome: job cannot be started

Modifying the manifest information manually
===========================================

Let's check the content of the manifest file:

.. code-block:: none

    $ cat /var/tmp/checkbox-ng/machine-manifest.json
	
    {
      "com.canonical.certification::has_touchscreen": false
    }

As you can see, it's a JSON file that stores the value for each of the entries
(only one in our case :)) we need to run our test plan.

Using your favorite text editor, open the file, replace ``false`` with
``true`` and save your modifications.

Run Checkbox again, following the same steps we have done so far, and you will
see in the System Manifest screen that ``Touchscreen`` is now set to ``Yes``.

It can be very useful to provide pre-filled manifest files, especially when
you want to automate Checkbox testing.

Skipping the System Manifest screen
===================================

So far, every time you started Checkbox to run this test plan, you were
greeted with the System Manifest screen to confirm the manifest information
was correct prior to starting the test.

Let's assume it is. Yes, our hypothetical test device has a touch screen,
and we want to execute the test plan right away.

First of all, make sure the information in the manifest file is correct:

.. code-block:: none

    $ cat /var/tmp/checkbox-ng/machine-manifest.json
	
    {
      "com.canonical.certification::has_touchscreen": true
    }

Next, create a launcher file named ``auto-manifest`` with the following content:

.. code-block:: none
    :caption: auto-manifest
    :name: auto-manifest
    :emphasize-lines: 11-12

    [launcher]
    launcher_version = 1

    [test plan]
    unit = com.canonical.certification::tutorial-base-manifest
    forced = yes
    
    [test selection]
    forced = yes
    
    [ui]
    type = silent

You have previously learned about most of the sections in this launcher. One
addition is the ``[ui]`` section, which covers customization related to
the user interface. ``type = silent`` means Checkbox will run everything
automatically. If there are any interactive jobs, they will be skipped. In
addition, the System Manifest screen will be skipped and the values from the
manifest file will be used. If the manifest file is absent, or if a required
entry is absent, Checkbox will assume its value is ``False``.

Now, run Checkbox using this launcher:

.. code-block:: none

    $ checkbox-cli launcher auto-manifest
    Preparing...
    Reports will be saved to: /home/user/.local/share/checkbox-ng
    =========[ Running job 1 / 3. Estimated time left (at least): 0:00:02 ]=========
    --------------------------[ A job that always passes ]--------------------------
    
    (...)
    
    =========[ Running job 2 / 3. Estimated time left (at least): 0:00:02 ]=========
    -----------------------------[ Hardware Manifest ]------------------------------
    
    (...)
    
    has_touchscreen: True
    
    (...)
    
    =========[ Running job 3 / 3. Estimated time left (at least): 0:00:01 ]=========
    ---------------------------[ A job using a manifest ]---------------------------
    ID: com.canonical.certification::tutorial/manifest
    Category: com.canonical.certification::tutorial
    ... 8< -------------------------------------------------------------------------
    This test is executed because user said this device has a touchscreen.
    ------------------------------------------------------------------------- >8 ---
    Outcome: job passed
     ☑ : A job that always passes
     ☑ : Hardware Manifest
     ☑ : A job using a manifest
    file:///home/user/.local/share/checkbox-ng/submission_2023-09-19T06.01.26.407098.html
    file:///home/user/.local/share/checkbox-ng/submission_2023-09-19T06.01.26.407098.junit.xml
    file:///home/user/.local/share/checkbox-ng/submission_2023-09-19T06.01.26.407098.tar.xz

Observe how the System Manifest screen was not displayed, and Checkbox started the test plan straight ahead. Moreover, the ``tutorial/manifest`` job was executed since the required information for it (``has_touchscreen``) has been set to ``true`` in the ``/var/tmp/checkbox-ng/machine-manifest.json`` manifest file.

Wrapping up
===========

In this section, you've learned what was the Checkbox manifest, how it was
used, where its information is stored and how to edit it to automate test
runs when some of the jobs in the test plan depend on a manifest entry.
