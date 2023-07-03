================================
 canonical-certification-server
================================

--------------------------------------------------------------------------------------------------------
performs interactive system testing in console mode and sends results to Canonical Certification Website
--------------------------------------------------------------------------------------------------------

:Manual section: 1
:Author: Jeffrey Lane, 2018-2023

SYNOPSIS
========
  For certifying bare metal servers (the most common scenario):
    certify-22.04 
    certify-20.04

  For certifying Systems on Chip (For SoC vendors):
    certify-soc-22.04
    certify-soc-20.04
  
  For certifying Ubuntu as a Guest on a Hypervisor:
    certify-vm-22.04
    certify-vm-20.04

  For running smaller subsets of the certification suite:
    test-cpu
    test-firmware
    test-memory
    test-network
    test-nvdimm
    test-iso-install
    test-storage
    test-stress
    test-usb
    test-virtualization

  Runs functional testing only, no stress test cases are executed:
    test-functional-22.04
    test-functional-20.04

OPTIONS
=======

This program doesn't support any command line options.

DESCRIPTION
===========

This program is meant for use with systems participating in the Canonical
hardware certification process. To submit results to Canonical for
certification purposes, the device under test must have a valid *Secure-ID*
number.  To learn how to create or locate the Secure ID, please see here:
https://certification.canonical.com/

This program will first gather information from your system. Next, it will run 
a series of automated test cases that test functionality and generate stress 
to test various subsystems.  When complete, you will be asked for the Secure 
ID of the computer to submit the information to the certification.canonical.com 
database.

Testers shoud run any of the certify-* commands to submit official
certification tests to Canonical.  Should retests be necessary, the tester will
be directed to run one of the retest commands by the Certification Team.
