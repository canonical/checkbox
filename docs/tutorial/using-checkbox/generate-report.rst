.. _generate-report:

============================
Customize test output format
============================

Checkbox generates test reports after executing test plans. These reports
usually include a summary in HTML and other submission files. You can also
customize how each test report should be generated for different use cases.

In Checkbox, the representation of a test report is controlled by two major
configurations in launcher: 

- ``exporter``: the format in which test report should be presented, such as
  text, HTML, JSON and others
- ``transporter``: the output destination of each representation, such as the
  standard output (``stdout``) or a file

In this tutorial, you will learn to use launcher configurations to save test
reports in local file, produce output in different formats and generate multiple
reports for one single test run.

For a more comprehensive overview about test reports, please refer to the
:ref:`test-report` section.


Save test reports to file
==========================

When Checkbox completes executing all test jobs, a test summary is displayed in
the running console in the textual form. For example, the following text is a
summary displayed after running the ``tutorial-base`` test plan:

.. code-block:: none
 
  ☑ : A job that always passes
  ☒ : A job that always fails
  ⚠ : A job that always crashes
  ☑ : A job that depends on other job that passes
  ☐ : A job that is skipped because it depends on a job that fails
  ☑ : A job that generates different resources for tutorial purposes
  ☑ : A job that requires a resource and it is available
  ☐ : A job that requires a resource but it's not available
  ☑ : A job that displays an environment variable, if set
  ☑ : A manual job
  ☑ : A semi-automated job where the outcome is set automatically
  ☑ : A semi-automated job where the user manually sets the outcome


It may be tempting to redirect this output to file manually, but it is possible
to save it in a file using the Checkbox ``transport`` configuration. 

The following example shows how to define a ``transport`` section in a launcher
file. In the section header, the colon symbol (``:``) leads the name of the
transport (``out_to_file``). The value ``type = file`` specifies that the output
is directed to a file that is located at the given path.

.. code-block:: ini
  
  [transport:out_to_file]
  type = file
  path = /tmp/output.txt

Similarly, you can also direct the output to the standard output as a stream:

.. code-block:: ini
  
  [transport:out_to_stdout]
  type = stream
  # standard out, you can also try "stderr" for standard error
  stream = stdout

However, the transport section is effective only if it is used in a ``report``
section. If you invoke Checkbox with either of the above sections in a launcher
file without further edit, it will not generate any extra output.

Now let's add a few more sections in the launcher to save the test summary to a
file. Try the following launcher:

.. code-block:: ini
  :caption: Save text report to file
  :emphasize-lines: 9-10, 17-19

  [test plan]
  unit = com.canonical.certification::tutorial-base
  forced = yes

  [test selection]
  forced = yes

  # ":" delimits the name of the exporter
  [exporter:text]
  unit = com.canonical.plainbox::text

  [transport:out_to_file]
  type = file
  path = /tmp/output.txt

  # define a custom report
  [report:file_report]
  exporter = text
  transport = out_to_file

In this example, you defined two new sections: 

- ``exporter``: named ``text``, specifies that the output unit being used is
  ``com.canonical.plainbox::text``. 
- ``report``: named ``file_report``, specifies that a customized report
  configuration is used. The customized report uses an exporter called ``text``
  and a transport called ``out_to_file``, which you defined in the same file.

Launch Checkbox, and after the jobs are completed, you should see a new line in
the console output:: 

  file:///tmp/output.txt

Now you have a text report to check at ``/tmp/output.txt``.

.. note::

  Checkbox will ask you if you want to submit the ``file_report`` report. This is
  a confirmation for producing the report. Respond yes.
  See the example below to know how to avoid having to give confirmation
  (using `forced`).

Export report in different formats 
===================================

If you want to process the test results in another application or visualize the
test report, you need to create representations other than the plain text form. 

In Checkbox, it is the ``exporter`` configuration that defines the form of
report output, including HTML, JSON, and other common formats. 

To view the supported types of exporters on your machine, run::

  $ checkbox.checkbox-cli list exporter

You might see a list similar to the following result:

.. code-block:: none

  exporter 'com.canonical.plainbox::html'
  exporter 'com.canonical.plainbox::html-multi-page'
  exporter 'com.canonical.plainbox::json'
  exporter 'com.canonical.plainbox::text'
  exporter 'com.canonical.plainbox::tar'
  exporter 'com.canonical.plainbox::xlsx'
  exporter 'com.canonical.plainbox::global'
  exporter 'com.canonical.plainbox::junit'
  exporter 'com.canonical.plainbox::tp-export'

Now let's configure Checkbox to generate a report in JSON for the same test
jobs. Create a new launcher:

.. code-block:: ini
  :caption: Save JSON report to file
  :emphasize-lines: 8-9, 13, 16

  [test plan]
  unit = com.canonical.certification::tutorial-base
  forced = yes

  [test selection]
  forced = yes

  [exporter:json]
  unit = com.canonical.plainbox::json

  [transport:out_to_file]
  type = file
  path = /tmp/output.json

  [report:file_report]
  exporter = json
  transport = out_to_file
  # This tells Checkbox to always produce this report
  # without asking any confirmation
  forced = yes

Run Checkbox again with the new launcher, a new file is generated at
``/tmp/output.json``. This JSON report contains much more detailed information
about the test job execution: 

.. code-block:: json

  {
    "title": "session title",
    "testplan_id": "com.canonical.certification::tutorial-base",
    "custom_joblist": false,
    "results": [
        {
            "id": "tutorial/crashing",
            "full_id": "com.canonical.certification::tutorial/crashing",
            "name": "A job that always crashes",
            "certification_status": "non-blocker",
            "category": "Tutorial",
            "category_id": "com.canonical.certification::tutorial",
            "status": "fail",
            "outcome": "crash",
            "comments": null,
            "io_log": "This job crashes because we run a command to kill it before it's finished.\n",
            "type": "test",
            "project": "certification",
            "duration": 0.23536920547485352,
            "plugin": "shell"
        },
        {
            "id": "tutorial/failing",
            "full_id": "com.canonical.certification::tutorial/failing",
            "name": "A job that always fails",
            "certification_status": "non-blocker",
            "category": "Tutorial",
            "category_id": "com.canonical.certification::tutorial",
            "status": "fail",
            "outcome": "fail",
            "comments": null,
            "io_log": "This job fails!\n",
            "type": "test",
            "project": "certification",
            "duration": 0.1324455738067627,
            "plugin": "shell"
        }
        // ...
    ]
  }


Generate multiple reports
============================

You can configure multiple exporters in the same launcher for different use
cases. When a test session is completed, you will obtain multiple reports for
the same test results. 

Try the following launcher to produce HTML, JSON and textual reports for the
same test results:

.. code-block:: ini

  [test plan]
  unit = com.canonical.certification::tutorial-base
  forced = yes

  [test selection]
  forced = yes

  # exporter
  [exporter:text]
  unit = com.canonical.plainbox::text

  [exporter:json]
  unit = com.canonical.plainbox::json

  [exporter:html]
  unit = com.canonical.plainbox::html

  # transport
  [transport:out_to_text]
  type = file
  path = ~/.last_result.txt

  [transport:out_to_json]
  type = file
  path = /tmp/upload.json

  [transport:out_to_html]
  type = file
  path = /tmp/upload.html

  # report
  [report:test_report]
  exporter = text
  transport = out_to_text
  forced = yes

  [report:json_report]
  exporter = json
  transport = out_to_json
  forced = yes

  [report:html_report]
  exporter = html
  transport = out_to_html
  forced = yes


Three files are generated when the test job are completed. Take a look at the
beautiful HTML report at the specified path::

  file:///tmp/upload.html
  file:///tmp/upload.json
  file:///home/user/.last_result.txt


.. note::

  If you start Checkbox with this launcher, remember that it will
  create a file in ``~/.last_result.txt``. You may want
  to remove it after this experiment.

Wrapping up
===========

Congratulations! You now know how to customize your test reports for various use
cases. If you want to learn more about the configurations in a launcher, see the
:doc:`../../reference/launcher` reference document.
