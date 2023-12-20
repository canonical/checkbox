:orphan: This document is built but not included in the table of content.

.. _test_output:

============================
Test output
============================

When Checkbox runs the tests, it generates a series of outputs, which include 
the ``ID`` and ``Category`` of the tests, along with the results of each of 
them (if a test ID fails, the cause for the failure would be displayed). 

Now we will introduce each section of the test output by performing a test 
for audio device detection in practice.

.. code-block:: none

    =========[ Running job 1 / 3. Estimated time left (at least): 0:00:01 ]=========

**Progress Indicator** shows the current status of the ongoing 
job, including the total number of jobs and the number completed. It also 
provides an estimated time left for completion, helping users track progress 
and estimate when the test will finish.


.. code-block:: none

    -----------------------------[ Hardware Manifest ]------------------------------

**Summary** provides a brief sentence to help users understand the purpose of 
this job. 

In this case, it's `Hardware Manifest
<https://checkbox.readthedocs.io/en/latest/reference/launcher.html
#manifest-section>`_, which provides information 
about various hardware devices used in the tests. When certain tests involve 
specific hardware devices, Checkbox will prompt users to inform in advance 
whether the machine includes specific hardware devices required for testing 
purposes.


.. code-block:: none

    ID: com.canonical.plainbox::manifest
    Category: com.canonical.plainbox::uncategorised

**ID** indicates the job IDs run during the test. and it's organised into 
different **Categories** based on their functionalities or characteristics.


.. code-block:: none

    ... 8< -------------------------------------------------------------------------
    ns: com.canonical.certification
    name: checkbox-provider-base
    has_audio_playback: False
    has_audio_capture: True
    
    ------------------------------------------------------------------------- >8 ---

This is the job stdout from ``com.canonical.plainbox::manifest``. If a job 
fails or is skipped, the message will also be shown in this section.

In our case, we are testing audio device detection, and the manifest was 
prompted earlier to ask for user-provided information, this section displays 
the collected information from the user.


.. code-block:: none

    Outcome: job passed

At the end of each test, the **Outcome** will be displayed to indicate whether 
the test has passed.


.. code-block:: none

    ------------[ Check that at least one audio playback device exits ]-------------
    ID: com.canonical.certification::audio/detect-playback-devices
    Category: com.canonical.plainbox::audio
    Job cannot be started because:
     - resource expression "manifest.has_audio_playback == 'True'" evaluates to false
    Outcome: job cannot be started

Oops! Apparently this job was skipped.Based on the stdout, it seems that this 
issue occurred because when Checkbox asking hardware manifest, we mistakenly 
set ``has_audio_playback`` to ``False``. Consequently, Checkbox determined that 
the machine lacks the necessary audio devices to support the test.


.. code-block:: none

      ☑ : Hardware Manifest
      ☐ : Check that at least one audio playback device exits
      ☑ : Check that at least one audio capture device exists
      
After all the jobs are completed, a checklist will summarise the results of 
each test.


.. code-block:: none

    file:///home/user/.local/share/checkbox-ng/submission_2023-07-25T07.53.41.800141.html
    file:///home/user/.local/share/checkbox-ng/submission_2023-07-25T07.53.41.800141.junit.xml
    file:///home/user/.local/share/checkbox-ng/submission_2023-07-25T07.53.41.800141.tar.xz
  
Checkbox collect all data related to the test and generates a **Test Reports** 
locally.


.. code-block:: none

    Do you want to submit 'upload to certification' report?
      y => yes
      n => no

Users would be asked whether they want to upload the results to the Canonical 
:term:`Certification website`.

Congrats! Now you have a basic understanding 
of the test output.

