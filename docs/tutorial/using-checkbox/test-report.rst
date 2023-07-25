.. _test-report:

Review Test Report 
======================

Checkbox optionally generates test reports in different formats that can be used to easily share the results of a test session. Generally, a :ref:`text summary<test-summary>` and :ref:`submission files<submission-files>` would be created. In this section, you will learn where to find the report files and what they contain.

Note that you can tailor desired reports in your launcher file, or define your own exporter to customize the reports. See :doc:`launcher<../../reference/launcher>` and :doc:`exporter<../../reference/units/exporter>` for more details.

.. _test-summary:
Text summary
------------

A text summary shows in the console once all jobs complete, providing an overview of test result. You can find the result of each job displaying in a form of ``outcome: summary``.

Example:

.. code-block:: none

     ☐ : Resource for NVDIMM detection
     ☑ : Display USB devices attached to SUT
     ☒ : Test USB 2.0 or 1.1 ports
     ☑ : Collect information about supported types of USB
     ☒ : Test USB 3.0 or 3.1 ports

Types of job's outcome defined in Checkbox:

    ``​ ​`` job didn't run

    ``☑`` job passed

    ``☒`` job failed

    ``☐`` job skipped, job cannot be started

    ``‒`` job is not implemented

    ``⁇`` job needs verification

    ``⚠`` job crashed

.. _submission-files:
Submission files
------------

In Checkbox, the submission files are used for sharing test results to Jenkins and Certification Website. Submission files contain the following files:

.. code-block:: none

    ├── html
    ├── junit
    └── tar
         ├── html
         ├── json
         ├── junit
         └── attachments


The absolute paths of submission files show in console after the text summary block.

Example:

.. code-block:: none

    file:///home/user/.local/share/checkbox-ng/submission.html
    file:///home/user/.local/share/checkbox-ng/submission.junit.xml
    file:///home/user/.local/share/checkbox-ng/submission.tar.xz

``html``
    Self-contained HTML files contain the following sections.

        - System Information
        - Tests Results 
        - Logs

.. figure:: ../../_images/checkbox-test-report.png
    
    An example of beginning of a HTML report

``json``
    JSON files contain session export compatible for submission to Certification Website.

``junit``
    JUnit XML files contain test data that can be read by Jenkins.

``tar``
    Xz compressed tarball of the HTML, JUnit and JSON reports. Also contains all the attachments (I/O logs and binary files). Certification Website only accepts submissions tarballs, from which it extracts the submission.json file to create a new test report in the database.