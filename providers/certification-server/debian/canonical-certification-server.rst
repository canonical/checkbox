================================
 canonical-certification-server
================================

--------------------------------------------------------------------------------------------------------
performs interactive system testing in console mode and sends results to Canonical Certification Website
--------------------------------------------------------------------------------------------------------

:Manual section: 1
:Author: Jeffrey Lane, 2018

SYNOPSIS
========
  For certifying bare metal servers, and most certification test scenaros:
    certify-16.04 
    certify-14.04

  For certifying Systems on Chip:
    certify-soc-16.04
    certify-soc-14.04
  
  For certifying Ubuntu as a Guest on a Hypervisor:
    certify-vm-16.04
    certify-vm-14.04

  Abbreviated functional test that does not include lengthy stress tests:
    test-functional-14.04

  Retest commands for running retests on a specific subsystem:
    test-network-14.04
    test-network-16.04
    test-storage
    test-virtualziation
    test-firmware
    test-usb

  Runs functional testing only, no stress test cases are executed:
    test-functional-16.04
    test-functional-14.04

  Runs checkbox-cli with full list of test plans and cases to select:
    canonical-certification-server

OPTIONS
=======

This program doesn't support any command line options.

DESCRIPTION
===========

This program is meant for use with systems participating in the Canonical
hardware certification process. To use this tool the device under test must
have a valid *Secure-ID* number.  To learn how to create or locate the Secure
ID, please see here: https://certification.canonical.com/

This program will gather information from your system. Then you will be asked
manual tests to confirm that the system is working properly. Finally, you will
be asked for the Secure ID of the computer to submit the information to the
certification.canonical.com database.

Testers shoud run any of the certify-* commands to submit official
certification tests to Canonical.  Should retests be necessary, the tester will
be directed to run one of the retest commands by the Certification Team.

TEST PLAN SELECTION
===================

The command 'canonical-certification-server' will allow you to select test any
test plan. The other commands will launch certification without the ability to 
alter selections and these are the commands that should be used for 
certification testing unless otherwise instructed.
