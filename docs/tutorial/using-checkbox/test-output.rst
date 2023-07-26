.. _test_output:

============================
Test output
============================

When Checkbox runs the tests, it generates a series of outputs, which include the ID and category of the tests, along with the results of each them (if a test ID fails, the cause for the failure would be displayed). 

The test output can be generally divided into the following sections:

- **Hardware Manifest**:
  
  Some tests rely on the user's manual confirmation of hardware devices on the machine. This section lists the user's confirmation results.

- **Test ID**:
  
  This section contains all the test IDs run during the test. Each test ID has its own separate section indicating the logs and test results during the test.

- **Outcome**:
  
  This section indicate the test results of test IDs.
  
- **Summary**:

  Graphical icons is used to indicate the results of each test IDs.

- **Test Reports**:
  
  Checkbox collects all data related to the test and generates a test report in local.

- **Submit Results**:
  
  Users are asked whether they want to upload the results to the Canonical :term:`Certification website`.
  

Now that you have a basic understanding of the test output, here is an example of audio detect tests for practice:

.. code-block:: none

    =========[ Running job 1 / 3. Estimated time left (at least): 0:00:01 ]=========
    -----------------------------[ Hardware Manifest ]------------------------------
    ID: com.canonical.plainbox::manifest
    Category: com.canonical.plainbox::uncategorised
    ... 8< -------------------------------------------------------------------------
    ns: com.canonical.certification
    name: checkbox-provider-base
    has_audio_playback: False
    has_audio_capture: True
    
    ------------------------------------------------------------------------- >8 ---
    Outcome: job passed
    =========[ Running job 2 / 3. Estimated time left (at least): 0:00:01 ]=========
    ------------[ Check that at least one audio playback device exits ]-------------
    ID: com.canonical.certification::audio/detect-playback-devices
    Category: com.canonical.plainbox::audio
    Job cannot be started because:
     - resource expression "manifest.has_audio_playback == 'True'" evaluates to false
    Outcome: job cannot be started
    =========[ Running job 3 / 3. Estimated time left (at least): 0:00:00 ]=========
    ------------[ Check that at least one audio capture device exists ]-------------
    ID: com.canonical.certification::audio/detect-capture-devices
    Category: com.canonical.plainbox::audio
    ... 8< -------------------------------------------------------------------------
    Count: 4
    ------------------------------------------------------------------------- >8 ---
    Outcome: job passed
      ☑ : Hardware Manifest
      ☐ : Check that at least one audio playback device exits
      ☑ : Check that at least one audio capture device exists

    file:///home/user/.local/share/checkbox-ng/submission_2023-07-25T07.53.41.800141.html
    file:///home/user/.local/share/checkbox-ng/submission_2023-07-25T07.53.41.800141.junit.xml
    file:///home/user/.local/share/checkbox-ng/submission_2023-07-25T07.53.41.800141.tar.xz
    Do you want to submit 'upload to certification' report?
      y => yes
      n => no

.. note::

    If a hardware device required by a test ID is identified as ``False`` by the user, the test will be skipped.
