# TGPIO Testing Guide

## Introduction

TGPIO stands for Time-aware General-Purpose Input/Output. It is like GPIO but is used to transmit timestamps for synchronizing time.

## Prerequisites

### Hardware

To perform the TGPIO test, we need two machines. We recommend testing with two identical machines to ensure consistent results.
One machine will act as the server to send timestamps, and the other as the DUT (Device Under Test) to receive timestamps.
Alternatively, you can test both send and receive on one machine.

**Connect the corresponding TGPIO pins on these two machines.**

### Software

#### On the Server

To start sending timestamps, we need to run the server script.

1. Check your PTP device node by referring the job `ptp-device-node-info`.
2. Determine the PTP device pin number. The number of TGPIO pins on the machine will affect this.
3. Run the server script in server mode:

   1. Enter the checkbox environment: `sudo checkbox.shell`
   2. Run the script: `python3 /snap/checkbox22/current/providers/checkbox-provider-base/bin/tgpio.py -r server -d {PTP_DEVICE_NODE} -p {PTP_DEVICE_PIN}`

#### On the DUT

Set up how many TGPIO pins you have.

1. `sudo checkbox.configure TGPIO_PIN_COUNT={NUMBER}`

For example, if you have 2 TGPIO pins, you should run

```terminal
sudo checkbox.configure TGPIO_PIN_COUNT=2
```

## Start the test

Until now, we are ready to perform the TGPIO tests.
