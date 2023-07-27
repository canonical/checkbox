.. _test-report:

Review Test Report 
==================

Once you finish your first test run, you may want to review the test reports. Checkbox generates test reports in different formats that can be used to easily share the results of a test session. By default, a :ref:`text summary<text-summary>` and :ref:`submission files<submission-files>` are created. This section will provide you with information on where to locate the report files and their respective contents.

.. note::

    You can tailor desired reports in your launcher file, or define your own exporter to customize the reports. See :doc:`launcher<../../reference/launcher>` and :doc:`exporter<../../reference/units/exporter>` for more details.

.. _text-summary:

Text Summary
------------

You should see a text summary displayed in the console once all jobs are completed. The result of each job is presented in the format: ``outcome: summary``. As it only provides an overview, for more in-depth information, you will need to review the :ref:`submission files<submission-files>`.

Example:

.. code-block:: none

     ☐ : Resource for NVDIMM detection
     ☑ : Display USB devices attached to SUT
     ☒ : Test USB 2.0 or 1.1 ports
     ☑ : Collect information about supported types of USB
     ☒ : Test USB 3.0 or 3.1 ports

Types of job's outcome defined in Checkbox:

.. list-table::
    :header-rows: 1
    :widths: 40 60

    * - symbol
      - outcome
    * - 
      - job didn't run
    * - ☑
      - job passed
    * - ☒
      - job failed
    * - ☐
      - job skipped, job cannot be started
    * - ‒
      - job is not implemented
    * - ⁇
      - job needs verification
    * - ⚠
      - job crashed

.. _submission-files:

Submission Files
----------------
 
In Checkbox, submission files encompass report files in various formats (HTML, JSON, and JUnit XML) along with attachments like I/O logs and binary files. These files serve the purpose of sharing test results with other users or services, such as Jenkins and :term:`Certification Website`. 

You can find absolute paths of submission files displayed in the console right after the text summary block. 

.. code-block:: none

    file:///home/user/.local/share/checkbox-ng/submission.html
    file:///home/user/.local/share/checkbox-ng/submission.junit.xml
    file:///home/user/.local/share/checkbox-ng/submission.tar.xz

Head to the folder ``~/.local/share/``, you should find submission files organized as follows:

.. code-block:: none

    ├── html
    ├── junit
    └── tar.xz
         ├── html
         ├── json
         ├── junit
         └── attachments

``html``
    Open HTML files with your preferred web browser, you will see a System Testing Report with the following sections.
    
    - System Information
    - Tests Results
    - Logs
    
    You can expand entries in Tests Results and Logs sections to access more detailed information. Additionally, you can utilize the search bar to filter specific tests for easier navigation.

.. figure:: ../../_images/checkbox-test-report.png
    
    An example of beginning of a HTML report

``json``
    JSON files store session exports that are compatible for submission to Certification Website.

``junit``
    `JUnit XML <https://windyroad.com.au/dl/Open%20Source/JUnit.xsd>`_ files contain test data that can be read by Jenkins.

``tar.xz``
    The xz compressed tarball is a comprehensive archive that includes the aforementioned reports and all associated attachments, such as I/O logs and binary files. You can extract the tarball with ``tar -xf sumbission.tar.xz -C /path/to/destination``.

    Certification Website only accepts submissions tarballs, from which it extracts the ``submission.json`` file to create a new test report in the database. 