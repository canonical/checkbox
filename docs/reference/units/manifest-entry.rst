.. _manifest_entry:

===================
Manifest Entry Unit
===================

A manifest entry unit describes a single entry in a *manifest* that describes
the machine or device under test. The purpose of each entry is to define one
specific fact. Checkbox uses such units to create a manifest that associates
each entry with a value.

The values themselves can come from multiple sources, the simplest one is the
test operator who can provide an answer. In more complex cases a specialized
application might look up the type of the device using some identification
method (such as DMI data) from a server, thus removing the extra interaction
steps.

File format and location
------------------------

Manifest entry units are regular Checkbox units and are contained and shipped
with Checkbox providers. In other words, they are just the same as job and test
plan units, for example.

Fields
------

Following fields may be used by a manifest entry unit.

.. _Manifest Entry id field:

``id``:
    (mandatory) - Unique identifier of the entry. This field is used to look up
    and store data so please keep it stable across the lifetime of your
    provider.

.. _Manifest Entry name field:

``name``:
    (mandatory) - A human readable name of the entry. This should read as in a
    feature matrix of a device in a store (e.g., "802.11ac wireless
    capability", or "Thunderbolt support", "Number of hard drive bays"). This
    is not a sentence, don't end it with a dot. Please capitalize the first
    letter. The name is used in various listings so it should be kept
    reasonably short.

    The name is a translatable field so please prefix it with ``_`` as in
    ``_name: Example``.

.. _Manifest Entry value-type field:

``value-type``:
    (mandatory) - Type of value for this entry. Currently two values are
    allowed: ``bool`` for a yes/no value and ``natural`` for any natural number
    (negative numbers are rejected).

.. _Manifest Entry value-units field:

``value-units``:
    (optional) - Units in which value is measured in. This is only used when
    ``value-type`` is equal to ``natural``. For example a *"Screen size"*
    manifest entry could be measured in *"inch"* units.

.. _Manifest Entry resource-key field:

``resource-key``:
    (optional) - Name of the resource key used to store the manifest value when
    representing the manifest as a resource record. This field defaults to the
    so-called *partial id* which is just the ``id:`` field as spelled in the
    unit definition file (so without the name space of the provider)

.. _Manifest Entry prompt field:

``prompt``:
    (optional) - Allows the manifest unit to customize the prompt presented
    when collecting values from a user. When the ``value-type`` is ``bool`` the
    default prompt is "Does this machine have this piece of hardware?", when
    the ``value-type`` is ``natural`` the default prompt is "Please enter the
    requested data".

Example
-------

This is an example manifest entry definition::

    unit: manifest entry
    id: has_thunderbolt
    _name: Thunderbolt Support
    value-type: bool

Naming Manifest Entries
-----------------------

To keep the code consistent there's one naming scheme that should be followed.
Entries for boolean values must use the ``has_XXX`` naming scheme. This will
allow us to avoid issues later on where multiple people develop manifest
entries and it's all a bit weird what them mean ``has_thunderbolt`` or
``thunderbolt_supported`` or ``tb`` or whatever we come up with. It's a
convention, please stick to it.

Using Manifest Entries in Jobs
------------------------------

Manifest data can be used to decide if a given test is applicable for a given
device under test or not. When used as a resource they behave in a standard
way, like all other resources. The only special thing is the unique namespace
of the resource job as it is provided by Checkbox itself. The name of the
resource job is: ``com.canonical.plainbox``. In practice a simple job that
depends on data from the manifest can look like this::

    unit: job
    id: ...
    plugin: ...
    requires:
     manifest.has_thunderbolt == 'True' and manifest.ns == 'com.canonical.checkbox'
    imports: from com.canonical.plainbox import manifest

Note that the job uses the ``manifest`` job from the
``com.canonical.plainbox`` namespace. It has to be imported using the
``imports:`` field as it is in a different namespace than the one the example
unit is defined in (which is arbitrary). Having that resource, it can then check
for the ``has_thunderbolt`` field manifest entry in the
``com.canonical.checkbox`` namespace. Note that the namespace of the
``manifest`` job is not related to the ``manifest.ns`` value. Since any
provider can ship additional manifest entries and then all share the flat
namespace of resource attributes looking at the ``.ns`` attribute is a way to
uniquely identify a given manifest entry.

Collecting Manifest Data
------------------------

When running Checkbox, if some jobs in the selected test plan depend on a
manifest entry, a System Manifest screen will be presented so that the user
can define the value for each required manifest entries, for example:

.. code-block:: none

     System Manifest:
    ┌──────────────────────────────────────────────────────────────────────────────┐
    │ Does this machine have the following graphics ports?                         │
    │   DVI                                    ( ) Yes   ( ) No                    │
    │   DisplayPort                            ( ) Yes   ( ) No                    │
    │   HDMI                                   ( ) Yes   ( ) No                    │
    │   VGA                                    ( ) Yes   ( ) No                    │
    │ Does this machine have this piece of hardware?                               │
    │   A Wi-Fi Module                         ( ) Yes   ( ) No                    │
    │   A fingerprint reader                   ( ) Yes   ( ) No                    │
    │   An Ethernet Port                       ( ) Yes   ( ) No                    │
    │   Audio capture                          ( ) Yes   ( ) No                    │
    │   Audio playback                         ( ) Yes   ( ) No                    │
    │   Thunderbolt 3 Support                  ( ) Yes   ( ) No                    │
    │   Touchpad                               ( ) Yes   ( ) No                    │
    │   Touchscreen                            ( ) Yes   ( ) No                    │
    └──────────────────────────────────────────────────────────────────────────────┘
     Press (T) to start Testing                                      Shortcuts: y/n

User can quickly fill these by using the ``y`` and ``n`` keyboard shortcuts,
or highlight an entry and select the right answer using the arrow and the
``Space`` keys.

.. note::
    This screen will be skipped if Checkbox is set to run in silent mode
    (see :ref:`launcher_ui`). In this case, existing values from the manifest
    file (see below) will be used; if there is no value for a given entry,
    Checkbox will use ``False`` by default.

Supplying External Manifest
---------------------------

The manifest file is stored in ``/var/tmp/checkbox-ng/machine-manifest.json``.
If the provisioning method ships a valid manifest file there it can be used
for fully automated manifest-based deployments.

Here is an example of such a file:

.. code-block:: none

    {
      "com.canonical.certification::has_camera": false,
      "com.canonical.certification::has_dp": true,
      "com.canonical.certification::has_dvi": false,
      "com.canonical.certification::has_ethernet_adapter": true,
      "com.canonical.certification::has_hdmi": true,
      "com.canonical.certification::has_wlan_adapter": false
    }
