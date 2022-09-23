================================
 canonical-certification-submit
================================

----------------------------------------------------------------
sends a single submission to the Canonical Certification Website
----------------------------------------------------------------

:Manual section: 1
:Author: Zygmunt Krynicki, 2015

SYNOPSIS
========
  canonical-certification-submit <SUBMISSION>

OPTIONS
=======

--secure_id SECURE-ID	associate submission with a machine using this SECURE-ID

DESCRIPTION
===========

This program is a small convenience wrapper around the ``checkbox sumbit``
command.  It can be use to send a given submission file, typically an XML file
called ``submission.xml``, to the Canonical Certification Website.
