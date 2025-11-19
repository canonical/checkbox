Using groups
^^^^^^^^^^^^^^^

The ``group`` field lets you keep related jobs together and have the
dependency solver treat them as a single block. This is useful for
jobs that require a setup/teardown, or a sequence of jobs that
must not be interleaved with others.

Groups are not units, therefore a group id cannot be used in the ``include`` section
of a test plan. They are fields inside job units, like ``depends``, ``after`` or
``before``, and also serve the purpose of controlling execution order.

Key behaviors of groups
--------------------------

- Jobs in the same group are always run as a contiguous block.
- Dependencies between jobs **inside** the group are resolved normally.
- If a job **inside** the group depends on a job **outside**, the **whole group**
  depends on that outside job.
- If a job **outside** the group depends on a job **inside**, it depends on the
  **whole group**.
- If these group-level dependencies create a cycle, Checkbox outputs a dependency
  warning and removes the involved jobs from the test plan. 

Examples
--------

Setup/teardown structure
~~~~~~~~~~~~~~~~~~~~~~~~

The group field could be used to create a setup → tests → teardown structure,
where the setup and teardown jobs are part of the same group as the tests.

.. code-block::

    id: wireless_setup
    flags: simple
    group: group_wireless
    command: echo 'Setting up wireless tests' 

    id: wireless_test_1
    flags: simple
    group: group_wireless
    after: wireless_setup
    before: wireless_teardown
    command: echo 'Running wireless test 1'

    id: wireless_test_2
    flags: simple
    group: group_wireless
    after: wireless_setup
    before: wireless_teardown
    command: echo 'Running wireless test 2'

    id: wireless_teardown
    flags: simple
    group: group_wireless
    after: wireless_setup
    command: echo 'Tearing down wireless tests'

    id: wireless_test_plan
    name: wireless_test_plan
    unit: test plan
    _summary: Setup/teardown group test
    include:
      wireless_.*

Execution order::

    wireless_setup
    wireless_test_1
    wireless_test_2
    wireless_teardown

Step-by-step execution
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If we want to ensure a strict step-by-step execution order between jobs, even
if there are dependencies on other jobs, we can use groups to enforce that.

.. code-block::

    id: gather_device_info
    flags: simple
    command: echo "device_info" >> "$PLAINBOX_SESSION_SHARE"/device_info.txt

    id: device_insert
    flags: simple
    group: group_device
    command: echo "Inserting device"

    id: device_test_write 
    flags: simple
    group: group_device
    depends: gather_device_info device_insert
    command: echo "Testing device write"

    id: device_test_read
    flags: simple
    group: group_device
    after: device_test_write
    command: echo "Testing device read"

    id: device_remove
    flags: simple
    group: group_device
    after: device_test_read
    command: echo "Removing device"

    id: device_test_plan
    name: device_test_plan
    unit: test plan
    _summary: Step by step device test
    include:
      device_.*
      gather_device_info

Execution order::

    gather_device_info
    device_insert
    device_test_write
    device_test_read
    device_remove

.. note::
  
  Although `gather_device_info` is placed after the `device_*` jobs, it will be
  executed by Checkbox before them because `device_test_write` depends on it and
  because it's part of the `group_device` group like all the other `device_*` jobs.

Templated groups
~~~~~~~~~~~~~~~~

The group field can also be used in templated jobs.

.. note::
  
  Templated jobs can not be used as dependencies, See Instantiation in :ref:`Template unit<templates>`.

.. code-block::

   id: group_template_resource
   plugin: resource
   command:
       echo 'id: A'
       echo ''
       echo 'id: B'

   unit: template
   template-unit: job
   template-resource: group_template_resource
   id: test_{id}_1
   group: group_{id}
   flags: simple
   command: echo "Running test {id}_1"

   unit: template
   template-unit: job
   template-resource: group_template_resource
   id: test_{id}_2
   group: group_{id}
   flags: simple
   command: echo "Running test {id}_2"

   id: ordering_groups_template
   name: ordering_groups_template
   unit: test plan
   _summary: Templated group order test
   include:
     test_id_1
     test_id_2
   bootstrap_include:
     group_template_resource

Execution order::

    test_A_1
    test_A_2
    test_B_1
    test_B_2


Groups in jobs with the "also-after-suspend" flag
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The dependency manager can handle jobs with the "also-after-suspend"
flag inside groups.

.. note::
  
  Since `also-after-suspend` jobs make use of the `siblings` feature, they can not be used
  as dependencies. See Instantiation in :ref:`Template unit<templates>`.


.. code-block::

    id: test_A_1
    group: group_A
    flags: simple also-after-suspend
    command: echo "Running test 1"
    
    id: test_A_2
    group: group_A
    flags: simple also-after-suspend
    command: echo "Running test 2"
    
    id: test_B_1
    group: group_B
    flags: simple also-after-suspend
    command: echo "Running test 3"
    
    id: test_B_2
    group: group_B
    flags: simple also-after-suspend
    command: echo "Running test 4"
    
    id: after_suspend_groups
    name: after_suspend_groups
    unit: test plan
    _summary: after_suspend_groups
    include:
      .*test_.*

Execution order::

    test_A_1
    test_A_2
    test_B_1
    test_B_2
    sleep
    rtc
    suspend/suspend_advanced_auto
    after-suspend-test_A_1
    after-suspend-test_A_2
    after-suspend-test_B_1
    after-suspend-test_B_2