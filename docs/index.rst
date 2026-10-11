:relatedlinks: [Project&#32;repository](https://github.com/canonical/checkbox)

.. _home:

Checkbox
========

Checkbox is a testing framework used to validate device compatibility with
Ubuntu Linux.

It runs test plans made of test cases (or jobs) and generates test reports.
Jobs can be manual or automated. Any Linux command can be turned into a job.

Checkbox was developed as part of the `Ubuntu Certified`_ program. It runs
tests that ensure all the required features of a given device are working as
expected on Ubuntu Linux. It is compatible with any version of Ubuntu (Desktop,
Server, Core).

Checkbox is useful for anyone who wants to make sure their devices are running
as expected on Ubuntu.

---------

In this documentation
---------------------

Checkbox executes test plans: each test plan selects and orders jobs supplied by
providers. You can run plans locally or remotely, control test sessions with launchers and manifests, then review or submit the resulting reports.

Get started
~~~~~~~~~~~

Install Checkbox, run a test plan, and review the results of your first test
session.

* Tutorial: :doc:`Install Checkbox <tutorial/using-checkbox/installing-checkbox>` •   
  :doc:`Run a test plan <tutorial/using-checkbox/running-checkbox>` • 
  :doc:`Review a test report <tutorial/using-checkbox/test-report>`

Jobs and test plans
~~~~~~~~~~~~~~~~~~~

Checkbox defines test content as units. Jobs run test commands; test plans
select, generate, and order jobs; templates create jobs during bootstrap; and
categories classify them.

* **Concepts**: :doc:`Understanding Checkbox <explanation/understanding>` • 
  :doc:`Checkbox stack <reference/stack>` • 
  :doc:`Glossary <reference/glossary>`
* **Authoring**: :doc:`Writing a test case <tutorial/writing-tests/test-case>` •
  :doc:`Writing a test plan <tutorial/writing-tests/test-plan>` •
  :doc:`Nested test plans <how-to/nested-test-plan>` •
  :doc:`Matching jobs <how-to/using-match>` • 
  :doc:`Groups <how-to/using-groups>` •
  :doc:`Setup includes <how-to/using-setup-include>`
* **Reference**: :doc:`Job units <reference/units/job>` •
  :doc:`Test plan units <reference/units/test-plan>` •
  :doc:`Template units <reference/units/template>` •
  :doc:`Resource units <reference/units/resource>` •
  :doc:`Category units <reference/units/category>` •
  :doc:`Setup job units <reference/units/setup_job>` •
  :doc:`RFC822 format <reference/units/rfc822>`

Providers and custom frontends
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Providers contain test units and their supporting files. Develop and test a provider locally and then package a custom frontend for a particular project.

* **Integration**: :doc:`Side-load a provider <how-to/side-loading>`
* **Packaging**: :doc:`Create a custom frontend <tutorial/custom_frontend>` •
  :doc:`Custom frontend environment variables <how-to/custom-frontend-envvars>`
* **Reference**: :doc:`Packaging metadata <reference/units/packaging-meta-data>`

Running tests and remote control
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Run and control test sessions locally, or use a controller to run them on a
remote Checkbox agent.

* **Test sessions**: :doc:`Advanced commands <tutorial/using-checkbox/advanced-commands>` •
  :doc:`Job status <reference/job-status>` •
  :doc:`How Checkbox runs jobs <explanation/job-runners>`
* **Remote**: :doc:`Checkbox Remote <explanation/remote>` •
  :doc:`Run remote sessions <tutorial/using-checkbox/remote>` •
  :doc:`Agent service <how-to/agent-service>`

Launchers and manifests
~~~~~~~~~~~~~~~~~~~~~~~

Launchers tell Checkbox how to run a session; manifests describe the system so
Checkbox can select applicable test content.

* **Launchers**: :doc:`Use a launcher <tutorial/using-checkbox/launcher>` •
  :doc:`Automatic retries <how-to/launcher/auto-retry>` •
  :doc:`Output verbosity <how-to/launcher/output-verbosity>` •
  :doc:`Launcher reference <reference/launcher>`
* **Manifests**: :doc:`Use a manifest <tutorial/using-checkbox/manifest>` •
  :doc:`Manifest-entry units <reference/units/manifest-entry>`
* **Configuration**: :doc:`Configuration concepts <explanation/configs>` •
  :doc:`Configuration reference <reference/configuration>` •
  :doc:`Environment variables <reference/envvar>`

Reports and submission
~~~~~~~~~~~~~~~~~~~~~~

Review the outcome of a completed session, customise its report output, or
prepare its results for submission.

* **Review**: :doc:`Test reports <tutorial/using-checkbox/test-report>`
* **Generate**: :doc:`Customise report output <tutorial/using-checkbox/generate-report>` •
  :doc:`Exporter units <reference/units/exporter>`
* **Submit**: :doc:`Submission schema <reference/submission-schema>`

Checkbox maintenance and releases
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install and maintain Checkbox as a snap, control the version in use, and
follow its release processes.

* **Versions**: :doc:`Choose a snap <reference/snaps>` •
  :doc:`Freeze the Checkbox version <how-to/freeze-checkbox-version>`
* **Compatibility**: :doc:`Support for older Python <how-to/ancient-python>` •
  :doc:`Migrate away from Jinja2 <how-to/migrate-away-jinja2>`
* **Release process**: :doc:`Canary process <explanation/release_process/canary>` •  
  :doc:`Canary pipeline <explanation/release_process/canary_pipeline>` • 
  :doc:`Validation job example  <explanation/release_process/validation_job_example>` •
  :doc:`Validation pipeline execution  <explanation/release_process/validation_pipeline_execution>`

---------

How this documentation is organised
-----------------------------------

This documentation uses the `Diátaxis documentation structure
<https://diataxis.fr/>`_.

* :doc:`Tutorial <tutorial/index>` takes you step-by-step from installing
   Checkbox to writing test content and packaging a custom frontend.
* :doc:`How-to guides <how-to/index>` provide instructions for specific tasks
   such as side-loading providers and configuring sessions.
* :doc:`Reference <reference/index>` provides technical specifications for
   configuration, units, snaps, and report submissions.
* :doc:`Explanation <explanation/index>` provides conceptual context about
   Checkbox, its execution model, remote operation, and releases.

---------

Project and community
---------------------

Checkbox is a member of the Ubuntu family. It’s an open source project that
warmly welcomes community projects, contributions, suggestions, fixes and
constructive feedback.

* This project follows the `Ubuntu Code of Conduct`_
* :doc:`Get support <community/support>`
* :doc:`Report bugs <community/bugs>`
* :doc:`Contribute <community/contributing>`


.. toctree::
   :hidden:
   :maxdepth: 2

   tutorial/index
   how-to/index
   reference/index
   explanation/index

.. _Ubuntu Certified: https://ubuntu.com/certified
.. _Ubuntu Code of Conduct: https://ubuntu.com/community/ethos/code-of-conduct
