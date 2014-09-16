=======================
plainbox-file-units (7)
=======================

Synopsis
========

This page documents the Plainbox file units syntax and runtime behavior

Description
===========

The file unit is a internal implementation detail at this time.
It is technically a Unit but it currently cannot be defined in a unit definition
file as the 'unit: file' association is not exposed.

File units are useful as an abstraction that everything is an unit. It allows
the core to validate file properties (name, role, permissions) in context.
Currently the unit is very fresh and relatively under-used but it is expected
to replace many internal ad-hoc enumeration systems that deal with files.

File Fields
-----------

There are two fields that are used by the file unit:

``path``:
    This field defines the full, absolute path of the file that the unit is
    describing. Note that this is not an identifier as it is more natural to
    discuss files in terms of filenames rather than some abstract identifiers.

``role``:
    This field defines the purpose of the file in a given provider. This field
    may hold one of several supported values:
    
    'unit-source':
        The file is a source of unit definitions. Currently this is the only
        actually implemented value.

    'legacy-whitelist':
        This file is a legacy whitelist.
    
    'script':
        This file is an architecture independent executable.
        
    'binary':
        This file is an architecture-specific executable.
        
    'data':
        This file is a binary blob (a data file).
        
    'i18n':
        This file is a part of the internationalization subststem. Typically
        this would apply to the translation catalogues.
    
    'manage_py':
        This file is the provider management script, manage.py.
        
    'legal':
        This file contains copyright and licensing information.

    'docs':
        This file contains documentation.