.. _templates:

=============
Template Unit
=============

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

``template-engine``:
    Name of the template engine to use, default is python string formatting
    (See PEP 3101). Currently the only other supported engine is jinja2.

    This field is optional.

Instantiation
-------------

When a template is instantiated, a single record object is used to fill in the
parametric values to all the applicable fields. Each field is formatted using
the template-engine (default is python formatting language. Within each field
the record is exposed as the variable named by the ``template_resource`` field.
Record data is exposed as attributes of that object.

The special parameter ``__index__`` can be used to iterate over the devices
matching the ``template-filter`` field.

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

Here is a real life example of a template unit that generates a job for each
hard drive available on the system::

   unit: template
   template-resource: device
   template-filter: device.category == 'DISK'
   plugin: shell
   category_id: com.canonical.plainbox::disk
   id: disk/stats_{name}
   requires:
    device.path == "{path}"
    block_device.{name}_state != 'removable'
   user: root
   command: disk_stats_test {name}
   _description: This test checks {name} disk stats, generates some activity and rechecks stats to verify they've changed. It also verifies that disks appear in the various files they're supposed to.

The ``template-resource`` used here (``device``) refers to a resource job using
the ``udev_resource`` script to get information about the system. The
``udev_resource`` script returns a list of items with attributes such as
``path`` and ``name``, so we can use these directly in our template.

Simple Jinja templates example
------------------------------

Jinja2 can be used as the templating engine instead of python string formatting. This allows the author to access some powerful templating features including expressions.

First here is the previous disk stats example converted to jinja2::

    unit: template
    template-resource: device
    template-filter: device.category == 'DISK'
    template-engine: jinja2
    plugin: shell
    category_id: com.canonical.plainbox::disk
    id: disk/stats_{{ name }}
    requires:
    device.path == "{{ path }}"
    block_device.{{ name }}_state != 'removable'
    user: root
    command: disk_stats_test {{ name }}
    _description: This test checks {{ name }} disk stats, generates some activity and rechecks stats to verify they've changed. It also verifies that disks appear in the various files they're supposed to.

Template engine additional features
-----------------------------------

Plainbox populates the template parameter dictionary with some extra keys to aid the author.

``__index__``:
    If a template unit can result in N content jobs then this variable is equal to how many jobs have been created so far.

Following parameters are only available for ``template-engine``: ``jinja2``:

``__system_env__``:
    When checkbox encounters a template to render it will populate this variable with the executing shell's enviroment variables as ``os.environ``

``__on_ubuntucore__``:
    Helper function (boolean) checking if checkbox runs from on ubuntu core

``__checkbox_env__``:
    Dictionary containing the checkbox config environment section
