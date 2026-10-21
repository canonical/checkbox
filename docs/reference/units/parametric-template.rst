.. _parametric-templates:

========================
Parametric template unit
========================

A parametric template defines ordinary jobs using a fixed list of parameter
records.
Unlike a :ref:`template unit <templates>`, they use fixed parameters that do
not depend on the result of a  "resource job" result. Checkbox creates this 
jobs when loading the provider, before validation or execution.

.. code-block:: yaml

    unit: parametric template
    template-id: example
    parameters:
      - value: A
        number: 1
      - value: B
        number: 2
    id: example_{value}_{number}
    _summary: Test {value} with number {number}
    flags: [simple]
    command: 'true'

This definition creates two different jobs: ``example_A_1`` and ``example_B_2``.
Each pair of [value, number] creates one job.

Fields
======

.. program:: parametric template

.. option:: parameters

    Required list of mappings. Keys provide parameters for Python string
    formatting in job fields. Values may include numbers or lists.
    An empty list creates no jobs.

    YAML is the recommended format. PXU definitions can use a JSON list::

        parameters: [{"value": "A", "number": 1}, {"value": "B", "number": 2}]

.. option:: template-id

    Optional identifier for the source definition. If omitted, Checkbox derives
    it from the job ID pattern using the same rules as other template IDs. For
    example, ``example_{value}_{number}`` becomes ``example_value_number``.

    This identifier must be unique and cannot include a namespace. The provider
    namespace is added automatically.

All other fields are :ref:`ordinary job fields <job>`. The ``id`` field is the
pattern for generated job IDs. Each resolved ID must be unique. Use parameter
references in the ID, or ``{__index__}``, the one-based record index.

Parametric templates always generate jobs and use Python string formatting.
They do not accept other ``template-*`` fields, custom engines, resource
imports, or filters.

Instantiation and validation
============================

The provider retains the source definition and exposes the generated jobs.
Checkbox validates the actual parameter values with the ordinary job
validation checks. Contextual validation checks generated IDs for collisions and
resolves dependencies against the generated jobs.

Other jobs can reference concrete IDs in ``depends``, ``after``, and ``before``.
Siblings use the existing job sibling behavior. Job fields are interpolated
when accessed, preserving normal translation and execution behavior.

The records are fixed by the provider. Resource results and later bootstrap
steps do not change or regenerate this job set. A generated job may still use
``requires`` to control whether it can run; this does not supply expansion
records.

Discovery and selection
=======================

``checkbox-cli list 'parametric template'`` lists the source definitions.
``checkbox-cli show`` accepts the source's ``template-id`` or a generated
job's concrete ID. Source views retain the original definition; generated job
views show resolved fields.

Test plans can select concrete job IDs or the source's ``template-id`` to
select all its generated jobs. ``expand`` and ``list all-jobs`` expose generated
jobs and selected source definitions. ``list-bootstrapped`` lists selected
concrete jobs without resource-driven expansion.
