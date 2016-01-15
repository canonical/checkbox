===========================
plainbox-template-units (7)
===========================

Synopsis
========

This page documents the Plainbox template units syntax and runtime behavior

Description
===========

The template unit is a variant of Plainbox unit types. A template is a skeleton
for defining additional units, typically job definitions. A template is defined
as a typical RFC822-like Plainbox unit (like a typical job definition) with the
exception that all the fields starting with the string ``template-`` are
reserved for the template itself while all the other fields are a definition of
all the eventual instances of the template.

Template-Specific Fields
------------------------

There are four fields that are specific to the template unit:

``template-unit``:
    Name of the unit type this template will generate. By default job
    definition units are generated (as if the field was specified with the
    value of ``job``) eventually but other values may be used as well.

    This field is optional.

``template-resource``:
    Name of the resource job (if it is a compatible resource identifier) to use
    to parametrize the template. This must either be a name of a resource job
    available in the namespace the template unit belongs to *or* a valid
    resource identifier matching the definition in the ``template-imports``
    field.

    This field is mandatory.

``template-imports``:
    A resource import statement. It can be used to refer to arbitrary resource
    job by its full identifier and (optionally) give it a short variable name.

    The syntax of each imports line is::

        IMPORT_STMT ::  "from" <NAMESPACE> "import" <PARTIAL_ID>
                      | "from" <NAMESPACE> "import" <PARTIAL_ID>
                         AS <IDENTIFIER>

    The short syntax exposes ``PARTIAL_ID`` as the variable name available
    within all the fields defined within the template unit.  If it is not a
    valid variable name then the second form must be used.

    This field is sometimes optional. It becomes mandatory when the resource
    job definition is from another provider namespace or when it is not a valid
    resource identifier and needs to be aliased.

``template-filter``:
    A resource program that limits the set of records from which template
    instances will be made. The syntax of this field is the same as the syntax
    of typical job definition unit's ``requires`` field, that is, it is a
    python expression.

    When defined, the expression is evaluated once for each resource object and
    if it evaluates successfully to a True value then that particular resource
    object is used to instantiate a new unit.

    This field is optional.

Instantiation
-------------

When a template is instantiated, a single record object is used to fill in the
parametric values to all the applicable fields. Each field is formatted using
the python formatting language. Within each field the record is exposed as the
variable named by the ``template_resource`` field. Record data is exposed as
attributes of that object.

The special parameter ``__index__`` can be used to iterate over the devices
matching the ``template-filter`` field.

Migrating From Local Jobs
-------------------------

Migration from local jobs is mostly straightforward. Apart from one gotcha the
process is as follows:

1. Look at the data that was used to *instantiate* job definitions by the old
   local job. Write them down.
2. Ensure that all of the instantiated template data is exposed by exactly one
   resource. This may be the commonly-used checkbox ``device`` resource job or
   any custom resource job but it has to be all contained in one resource. Data
   that used to be computed partially by the resource and partially by the
   local job needs to be computed as additional attributes (fields) of the
   resource instead.
3. Replace the boilerplate of the local job (typically a ``cat``, here-document
   piped to ``run-templates`` and ``filter-templates``) with the equivalent
   ``template-resource`` and ``template-filter`` fields.
4. Remove the indentation so that all of the job definition is aligned to the
   left of the paragraph.
5. Re-validate the provider to ensure that everything looks okay.
6. Re-test the job by running it.

The only gotcha is related to step two. It is very common for local jobs to do
some additional computation. For example many storage tests compute the path
name of some ``sysfs`` file. This has to be converted to a readily-available
path that is provided by the resource job.

Another thing to remember is that Plainbox templates use Python syntax for
their fields. That means that some characters have to be escaped. For instance,
``${PLAINBOX_SESSION_SHARE}/test-file`` has to be escaped to
``${{PLAINBOX_SESSION_SHARE}}/test-file``.

Examples
========

Basic example
-------------

The following example contains a simplified template that instantiates to a
simple storage test. The test is only instantiated for devices that are
considered *physical*. In this example we don't want to spam the user with a
long list of loopback devices. This is implemented by exposing that data in the
resource job itself::

    id: device
    plugin: resource
    command:
        echo 'path: /dev/sda'
        echo 'has_media: yes'
        echo 'physical: yes'
        echo
        echo 'path: /dev/cdrom'
        echo 'has_media: no'
        echo 'physical: yes'
        echo
        echo 'path: /dev/loop0'
        echo 'has_media: yes'
        echo 'physical: no'

The template defines a test-storage-``XXX`` test where ``XXX`` is replaced by
the path of the device. Only devices which are *physical* according to some
definition are considered for testing. This means that the record related to
``/dev/loop0`` will be ignored and will not instantiate a test job for that
device. This feature can be coupled with the existing resource requirement to
let the user know that we did see their CD-ROM device but it was not tested as
there was no inserted media at the time::

   unit: template
   template-resource: device
   template-filter: device.physical == 'yes'
   requires: device.has_media == 'yes'
   id: test-storage-{path}
   plugin: shell
   command: perform-testing-on --device {path}

Real life example
-----------------

Here is a real life example from a provider. We have the following local job
that generates a job for each hard drive available on the system::

   plugin: local
   _summary: Check stats changes for each disk
   id: disk/stats
   requires: device.category == 'DISK'
   _description: 
    This test generates some disk activity and checks the stats to ensure drive
    activity is being recorded properly.
   command:
    cat <<'EOF' | run_templates -t -s 'udev_resource | filter_templates -w "category=DISK"'
    plugin: shell
    category_id: 2013.com.canonical.plainbox::disk
    id: disk/stats_`ls /sys$path/block`
    flags: deprecated
    requires:
     device.path == "$path"
     block_device.`ls /sys$path/block`_state != 'removable'
    user: root
    command: disk_stats_test `ls /sys$path/block | sed 's|!|/|'`
    description: This test checks disk stats, generates some activity and rechecks stats to verify they've changed. It also verifies that disks appear in the various files they're supposed to.
    EOF

After migration to a template unit job, it looks like this::

   unit: template
   template-resource: device
   template-filter: device.category == 'DISK'
   plugin: shell
   category_id: 2013.com.canonical.plainbox::disk
   id: disk/stats_{name}
   requires:
    device.path == "{path}"
    block_device.{name}_state != 'removable'
   user: root
   command: disk_stats_test {name}
   _description: This test checks {name} disk stats, generates some activity and rechecks stats to verify they've changed. It also verifies that disks appear in the various files they're supposed to.

The ``template-resource`` used here (``device``) refers to a resource job using the ``udev_resource`` script to get information about the system. The ``udev_resource`` script returns a list of items with attributes such as ``path`` and ``name``, so we can use these directly in our template.

We end up with a shorter (from 19 lines to 11!) and more readable template.
