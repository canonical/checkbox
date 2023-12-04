.. _submission_schema:

Submission Schema
==================

Checkbox :ref:`submissions <submission-files>` contain reports of the tests and in-depth information that helps analyzing the test results. These files are sent to the :term:`Certification Website` for sharing test results.

This document describes the schema of the ``submission.json`` files as part of the submission. To get the latest JSON schema file, go to the Checkbox `GitHub repository <https://github.com/canonical/checkbox/blob/main/submission-schema/schema.json>`_.

.. important:: 

    The schema described in this document is work-in-progress and being reviewed. If you need assistance in validating the schema, please contact the Checkbox team.
        
.. jsonschema:: ../../submission-schema/schema.json
    :lift_definitions:
    :auto_reference:
