Introduction
============

Client Certification Provider is a collection of tests for desktop hardware.

Naming conventions
------------------

PXU files containing test plans should use the following format::

    client-<PROGRAMME-TYPE>-<PROGRAMME-ID>-<IMAGE-TYPE>-<RELEASE>.pxu

for example::

    client-cert-odm-server-20.04.pxu

Description of parts:

+----------------+------------------------------------------------------+
| PROGRAMME-TYPE | If the contents are part of a Certification programme|
+----------------+------------------------------------------------------+
| PROGRAMME-ID   | Identifies the programme "desktop" or "iot" or "odm" |
+----------------+------------------------------------------------------+
| IMAGE-TYPE     | The type of image the test plans will be run on      |
|                | "desktop" or "server" or "ubuntucore"                |
+----------------+------------------------------------------------------+
| RELEASE        | Release/series number "18-04" or "18"                |
+----------------+------------------------------------------------------+
