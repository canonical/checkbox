===========================
plainbox-category-units (7)
===========================

Synopsis
========

This page documents the PlainBox category units syntax and runtime behavior

Description
===========

The category unit is a normalized implementation of a "test category" concept.
Using category units one can define logical groups of tests that deal with some
specific testing area (for example, suspend-resume or USB support).

Job definitions can be associated with at most one category. Categories can
be used by particular applications to facilitate test selection.

Category Fields
---------------

There are two fields that are used by the category unit:

``id``:
    This field defines the partial identifier of the category. It is similar
    to the id field on the job definition units.

    This field is mandatory.

``name``:
    This field defines a human readable name of the category. It may be used
    in application user interfaces for displaying a group of tests.

    This field is translatable.
    This field is mandatory.

Rationale
=========

The unit is a separate entity so that it can be shipped separately of job
definitions and so that it can gain a localizable name that can still be
referred to uniquely by any job definition.

In the future it is likely that the unit will be extended with additional
fields, for example to define an icon.

Note
====

Association between job definitions and categories can be overridden by
a particular test plan. Please refer to the test plan unit documentation for
details.

Examples
========

Given the following definition of a category unit::

    unit: category
    id: audio
    _name: Audio tests

And the following definition of a job unit::

    id: audio/speaker-headphone-plug-detection
    category_id: audio
    plugin: manual
    _description: Plug in your headphones and ensure the system detected them

The job definition will be a part of the audio category.