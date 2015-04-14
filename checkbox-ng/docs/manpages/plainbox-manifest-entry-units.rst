=================================
plainbox-manifest-entry-units (7)
=================================

Synopsis
========

This page documents the syntax of the plainbox manifest entry units

Description
===========

A manifest entry unit describes a single entry in a *manifest* that describes
the machine or device under test. The purpose of each entry is to define one
specific fact. Plainbox uses such units to create a manifest that associates
each entry with a value.

The values themselves can come from multiple sources, the simplest one is the
test operator who can provide an answer. In more complex cases a specialized
application might look up the type of the device using some identification
method (such as DMI data) from a server, thus removing the extra interaction
steps.

File format and location
------------------------

Manifest entry units are regular plainbox units and are contained and shipped
with plainbox providers. In other words, they are just the same as job and test
plan units, for example.

Fields
------

Following fields may be used by a manifest entry unit.

``id``:
    (mandatory) - Unique identifier of the entry. This field is used to look up
    and store data so please keep it stable across the lifetime of your
    provider.

``name``:
    (mandatory) - A human readable name of the entry. This should read as in a
    feature matrix of a device in a store (e.g., "802.11ac wireless
    capability", or "Thunderbolt support", "Number of hard drive bays"). This
    is not a sentence, don't end it with a dot. Please capitalize the first
    letter. The name is used in various listings so it should be kept
    reasonably short.

    The name is a translatable field so please prefix it with ``_`` as in
    ``_name: Example``.

``value-type``:
    (mandatory) - Type of value for this entry. Currently two values are
    allowed: ``bool`` for a yes/no value and ``natural`` for any natural number
    (negative numbers are rejected).

``value-units``:
    (optional) - Units in which value is measured in. This is only used when
    ``value-type`` is equal to ``natural``. For example a *"Screen size"*
    manifest entry could be measured in *"inch"* units.

``resource-key``:
    (optional) - Name of the resource key used to store the manifest value when
    representing the manifest as a resource record. This field defaults to the
    so-called *partial id* which is just the ``id:`` field as spelled in the
    unit definition file (so without the name space of the provider)

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
way, like all other resources. The only special thing is the unique name-space
of the resource job as it is provided by plainbox itself. The name of the
resource job is: ``2013.com.canonical.plainbox``. In practice a simple job that
depends on data from the manifest can look like this::

    unit: job
    id: ...
    plugin: ...
    requires:
     manifest.has_thunderbolt == 'True' and manifest.ns == '2013.com.canonical.checkbox'
    imports: from 2013.com.canonical.plainbox import manifest

Note that the job uses the ``manifest`` job from the
``2013.com.canonical.plainbox`` name-space. It has to be imported using the
``imports:`` field as it is in a different name-space than the one the example
unit is defined in (which is arbitrary). Having that resource it can then check
for the ``has_thunderbolt`` field manifest entry in the
``2013.com.canonical.checkbox`` name-space. Note that the name-space of the
``manifest`` job is not related to the ``manifest.ns`` value. Since any
provider can ship additional manifest entries and then all share the flat
name-space of resource attributes looking at the ``.ns`` attribute is a way to
uniquely identify a given manifest entry.

Collecting Manifest Data
------------------------

To interactively collect manifest data from a user please include this job
somewhere early in your test plan:
``2013.com.canonical.plainbox::collect-manifest``.

Supplying External Manifest
---------------------------

The manifest file is stored in
``$HOME/.local/share/plainbox/machine-manifest.json``.
If the provisioning method ships a valid manifest file there it can be used for
fully automatic but manifest-based deployments.
