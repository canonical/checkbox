#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
#
# Copyright (c) 2019, Intel Corporation. All rights reserved.
#
# Author: Marcin Maka <marcin.maka@linux.intel.com>

""" Parses manifests included in sof binary and prints extracted metadata
    in readable form.
"""

# pylint: disable=too-few-public-methods
# pylint: disable=too-many-arguments
# pylint: disable=too-many-instance-attributes

import sys
import argparse
import struct

# To extend the DSP memory layout list scroll down to DSP_MEM_SPACE_EXT

# Public keys signatures recognized by parse_css_manifest()
# - add a new one as array of bytes and append entry to KNOWN_KEYS below.

APL_INTEL_PROD_KEY = bytes(
    [
        0x1F,
        0xF4,
        0x58,
        0x74,
        0x64,
        0xD4,
        0xAE,
        0x90,
        0x03,
        0xB6,
        0x71,
        0x0D,
        0xB5,
        0xAF,
        0x6D,
        0xD6,
        0x96,
        0xCE,
        0x28,
        0x95,
        0xD1,
        0x5B,
        0x40,
        0x59,
        0xCD,
        0xDF,
        0x0C,
        0x55,
        0xD2,
        0xC1,
        0xBD,
        0x58,
        0xC3,
        0x0D,
        0x83,
        0xE2,
        0xAC,
        0xFA,
        0xE0,
        0xCC,
        0x54,
        0xF6,
        0x5F,
        0x72,
        0xC2,
        0x11,
        0x05,
        0x93,
        0x1D,
        0xB7,
        0xE4,
        0x4F,
        0xA4,
        0x95,
        0xF5,
        0x84,
        0x77,
        0x07,
        0x24,
        0x6E,
        0x72,
        0xCE,
        0x57,
        0x41,
        0xF2,
        0x0B,
        0x49,
        0x49,
        0x0C,
        0xE2,
        0x76,
        0xF8,
        0x19,
        0xC7,
        0x9F,
        0xE1,
        0xCA,
        0x77,
        0x20,
        0x1B,
        0x5D,
        0x1D,
        0xED,
        0xEE,
        0x5C,
        0x54,
        0x1D,
        0xF6,
        0x76,
        0x14,
        0xCE,
        0x6A,
        0x24,
        0x80,
        0xC9,
        0xCE,
        0x2E,
        0x92,
        0xE9,
        0x35,
        0xC7,
        0x1A,
        0xE9,
        0x97,
        0x7F,
        0x25,
        0x2B,
        0xA8,
        0xF3,
        0xC1,
        0x4D,
        0x6B,
        0xAE,
        0xD9,
        0xCD,
        0x0C,
        0xBB,
        0x08,
        0x6D,
        0x2B,
        0x01,
        0x44,
        0xE2,
        0xB9,
        0x44,
        0x4E,
        0x4D,
        0x5C,
        0xDF,
        0x8A,
        0x89,
        0xA5,
        0x3C,
        0x27,
        0xA0,
        0x54,
        0xDE,
        0xC5,
        0x5B,
        0xDE,
        0x58,
        0x10,
        0x8C,
        0xAA,
        0xC4,
        0x37,
        0x5B,
        0x73,
        0x58,
        0xFB,
        0xE3,
        0xCF,
        0x57,
        0xF5,
        0x65,
        0xD3,
        0x19,
        0x06,
        0xED,
        0x36,
        0x47,
        0xB0,
        0x91,
        0x67,
        0xEC,
        0xC1,
        0xE1,
        0x7B,
        0x4F,
        0x85,
        0x66,
        0x61,
        0x31,
        0x99,
        0xFC,
        0x98,
        0x7A,
        0x56,
        0x70,
        0x95,
        0x85,
        0x52,
        0xA0,
        0x30,
        0x37,
        0x92,
        0x11,
        0x9E,
        0x7F,
        0x33,
        0x44,
        0xD3,
        0x81,
        0xFD,
        0x14,
        0x74,
        0x51,
        0x1C,
        0x01,
        0x14,
        0xC8,
        0x4B,
        0xF6,
        0xD6,
        0xEB,
        0x67,
        0xEF,
        0xFC,
        0x0A,
        0x5F,
        0xCC,
        0x31,
        0x73,
        0xF8,
        0xA9,
        0xE3,
        0xCB,
        0xB4,
        0x8B,
        0x91,
        0xA1,
        0xF0,
        0xB9,
        0x6E,
        0x1F,
        0xEA,
        0xD3,
        0xA3,
        0xE4,
        0x0F,
        0x96,
        0x74,
        0x3C,
        0x17,
        0x5B,
        0x68,
        0x7C,
        0x87,
        0xFC,
        0x90,
        0x10,
        0x89,
        0x23,
        0xCA,
        0x5D,
        0x17,
        0x5B,
        0xC1,
        0xB5,
        0xC2,
        0x49,
        0x4E,
        0x2A,
        0x5F,
        0x47,
        0xC2,
    ]
)

CNL_INTEL_PROD_KEY = bytes(
    [
        0x41,
        0xA0,
        0x3E,
        0x14,
        0x1E,
        0x7E,
        0x29,
        0x72,
        0x89,
        0x97,
        0xC2,
        0xA7,
        0x7D,
        0xBC,
        0x1D,
        0x25,
        0xF4,
        0x9A,
        0xA8,
        0xB7,
        0x89,
        0x10,
        0x73,
        0x31,
        0x58,
        0xBD,
        0x46,
        0x55,
        0x78,
        0xCF,
        0xD9,
        0xE1,
        0x7D,
        0xFA,
        0x24,
        0x23,
        0xFA,
        0x5C,
        0x7C,
        0xC9,
        0x3D,
        0xC8,
        0xB5,
        0x74,
        0x87,
        0xA,
        0x8C,
        0xE7,
        0x33,
        0xC2,
        0x71,
        0x26,
        0xB1,
        0x4D,
        0x32,
        0x45,
        0x23,
        0x17,
        0xCB,
        0xA6,
        0xA2,
        0xD0,
        0xCC,
        0x9E,
        0x2B,
        0xA6,
        0x9,
        0x42,
        0x52,
        0xF1,
        0xE6,
        0xBD,
        0x73,
        0x92,
        0x2A,
        0xFB,
        0x7F,
        0xC4,
        0x8D,
        0x5,
        0xEC,
        0x69,
        0x7F,
        0xD4,
        0xA2,
        0x6C,
        0x46,
        0xD4,
        0x5D,
        0x92,
        0x1D,
        0x17,
        0x75,
        0x39,
        0x16,
        0x4C,
        0x61,
        0xA8,
        0xDA,
        0x93,
        0xD6,
        0x26,
        0x23,
        0xA,
        0xC8,
        0x2D,
        0xCC,
        0x81,
        0xF4,
        0xCC,
        0x85,
        0x42,
        0xAA,
        0xA3,
        0x15,
        0x8,
        0x62,
        0x8F,
        0x72,
        0x9B,
        0x5F,
        0x90,
        0x2F,
        0xD5,
        0x94,
        0xDC,
        0xAD,
        0xF,
        0xA9,
        0x8,
        0x8C,
        0x2E,
        0x20,
        0xF4,
        0xDF,
        0x12,
        0xF,
        0xE2,
        0x1E,
        0xEB,
        0xFB,
        0xF7,
        0xE9,
        0x22,
        0xEF,
        0xA7,
        0x12,
        0x3D,
        0x43,
        0x3B,
        0x62,
        0x8E,
        0x2E,
        0xEB,
        0x78,
        0x8,
        0x6E,
        0xD0,
        0xB0,
        0xEA,
        0x37,
        0x43,
        0x16,
        0xD8,
        0x11,
        0x5A,
        0xB5,
        0x5,
        0x60,
        0xF2,
        0x91,
        0xA7,
        0xAA,
        0x7D,
        0x7,
        0x17,
        0xB7,
        0x5B,
        0xEC,
        0x45,
        0xF4,
        0x4A,
        0xAF,
        0x5C,
        0xA3,
        0x30,
        0x62,
        0x8E,
        0x4D,
        0x63,
        0x2,
        0x2,
        0xED,
        0x4B,
        0x1F,
        0x1B,
        0x9A,
        0x2,
        0x29,
        0x9,
        0xC1,
        0x7A,
        0xC5,
        0xEB,
        0xC7,
        0xDB,
        0xA1,
        0x6F,
        0x61,
        0x31,
        0xFA,
        0x7B,
        0x3B,
        0xE0,
        0x6A,
        0x1C,
        0xEE,
        0x55,
        0xED,
        0xF0,
        0xF9,
        0x7A,
        0xAF,
        0xAA,
        0xC7,
        0x76,
        0xF5,
        0xFB,
        0x6A,
        0xBC,
        0x65,
        0xDE,
        0x42,
        0x3E,
        0x1C,
        0xDF,
        0xCC,
        0x69,
        0x75,
        0x1,
        0x38,
        0x8,
        0x66,
        0x20,
        0xEA,
        0x6,
        0x91,
        0xB8,
        0xCD,
        0x1D,
        0xFA,
        0xFD,
        0xE8,
        0xA0,
        0xBA,
        0x91,
    ]
)

ICL_INTEL_PROD_KEY = bytes(
    [
        0x63,
        0xDF,
        0x54,
        0xE3,
        0xC1,
        0xE5,
        0xD9,
        0xD2,
        0xB8,
        0xB5,
        0x13,
        0xB3,
        0xEC,
        0xC2,
        0x64,
        0xB5,
        0x16,
        0xB4,
        0xFC,
        0x56,
        0x92,
        0x67,
        0x17,
        0xC7,
        0x91,
        0x7B,
        0x3D,
        0xB0,
        0x22,
        0xBF,
        0x7F,
        0x92,
        0x39,
        0x35,
        0xCC,
        0x64,
        0x1C,
        0xAD,
        0x8,
        0x75,
        0xE7,
        0x67,
        0xB,
        0x8,
        0xF8,
        0x57,
        0xDB,
        0x9C,
        0xDE,
        0xAB,
        0xE,
        0xBD,
        0x27,
        0x5F,
        0x5,
        0x51,
        0xCF,
        0x6E,
        0x3E,
        0xC9,
        0xDD,
        0xE6,
        0x51,
        0x14,
        0x57,
        0xE1,
        0x8A,
        0x23,
        0xAE,
        0x7A,
        0xA5,
        0x5F,
        0xDC,
        0x16,
        0x13,
        0x1B,
        0x28,
        0x3B,
        0xAB,
        0xF1,
        0xC3,
        0xB5,
        0x73,
        0xC0,
        0x72,
        0xD8,
        0x86,
        0x7A,
        0x76,
        0x3A,
        0x2,
        0xBE,
        0x2F,
        0x3E,
        0xFE,
        0x93,
        0x83,
        0xA1,
        0xD,
        0xA0,
        0xFC,
        0x26,
        0x7F,
        0x6B,
        0x2E,
        0x5A,
        0xFD,
        0xAC,
        0x6B,
        0x53,
        0xD3,
        0xB8,
        0xFF,
        0x5E,
        0xC7,
        0x5,
        0x25,
        0xFF,
        0xE7,
        0x78,
        0x9C,
        0x45,
        0xE4,
        0x17,
        0xBD,
        0xF4,
        0x52,
        0x4E,
        0x3C,
        0xA2,
        0xA,
        0x4D,
        0x54,
        0xB5,
        0x40,
        0x30,
        0xB3,
        0x48,
        0xBA,
        0x6C,
        0xFA,
        0x63,
        0xC0,
        0x65,
        0x2E,
        0xDE,
        0x9,
        0x2E,
        0xA1,
        0x95,
        0x85,
        0xC0,
        0x78,
        0xD9,
        0x98,
        0x64,
        0x3C,
        0x29,
        0x2E,
        0x48,
        0x66,
        0x1E,
        0xAF,
        0x1D,
        0xA0,
        0x7C,
        0x15,
        0x3,
        0x7F,
        0x9E,
        0x5F,
        0x38,
        0xF5,
        0xC1,
        0xE1,
        0xE9,
        0xBE,
        0x77,
        0xA2,
        0x9C,
        0x83,
        0xF2,
        0x25,
        0x54,
        0x22,
        0xFE,
        0x29,
        0x66,
        0x5,
        0xC2,
        0xC9,
        0x6B,
        0x8B,
        0xA6,
        0xA3,
        0xF9,
        0xB1,
        0x6B,
        0xAF,
        0xE7,
        0x14,
        0x77,
        0xFF,
        0x17,
        0xC9,
        0x7C,
        0x7C,
        0x4E,
        0x83,
        0x28,
        0x2A,
        0xE5,
        0xC3,
        0xCC,
        0x6E,
        0x25,
        0xA,
        0x62,
        0xBB,
        0x97,
        0x44,
        0x86,
        0x7C,
        0xA2,
        0xD4,
        0xF1,
        0xD4,
        0xF8,
        0x8,
        0x17,
        0xF4,
        0x6C,
        0xCC,
        0x95,
        0x99,
        0xD4,
        0x86,
        0x37,
        0x4,
        0x9F,
        0x5,
        0x76,
        0x1B,
        0x44,
        0x55,
        0x75,
        0xD9,
        0x32,
        0x35,
        0xF1,
        0xEC,
        0x4D,
        0x93,
        0x73,
        0xE6,
        0xC4,
    ]
)

JSL_INTEL_PROD_KEY = bytes(
    [
        0x6F,
        0xE4,
        0xD5,
        0xC9,
        0x52,
        0xF4,
        0x01,
        0xC1,
        0x89,
        0xC7,
        0x2B,
        0x16,
        0x9B,
        0xE6,
        0x5D,
        0x8E,
        0x91,
        0x28,
        0x63,
        0x16,
        0x4F,
        0x7B,
        0x18,
        0x6E,
        0xA7,
        0x89,
        0x0C,
        0xEA,
        0x24,
        0x62,
        0xC7,
        0x94,
        0x75,
        0x43,
        0xFD,
        0x6D,
        0xA8,
        0x67,
        0x47,
        0x36,
        0x50,
        0xAF,
        0x37,
        0x46,
        0x15,
        0x82,
        0x45,
        0x4A,
        0xA3,
        0x2E,
        0xAE,
        0xA4,
        0x1F,
        0x92,
        0x67,
        0x4B,
        0x5E,
        0x67,
        0x7E,
        0x02,
        0xFC,
        0x18,
        0x6F,
        0x68,
        0x0D,
        0xE3,
        0xC1,
        0x00,
        0xDF,
        0xEA,
        0xED,
        0x9F,
        0xDC,
        0x61,
        0xA0,
        0xFD,
        0x36,
        0x61,
        0x84,
        0xA7,
        0x8C,
        0x2A,
        0x4B,
        0x2C,
        0x2D,
        0xED,
        0x8D,
        0x0B,
        0x35,
        0xE9,
        0x79,
        0x59,
        0x3F,
        0x22,
        0xDC,
        0x3C,
        0xD4,
        0x43,
        0x32,
        0x22,
        0xF0,
        0xDA,
        0x0D,
        0xA1,
        0x3A,
        0xEC,
        0x47,
        0x87,
        0x5E,
        0xA0,
        0xD2,
        0xAA,
        0xF8,
        0x1C,
        0x61,
        0x08,
        0x05,
        0x64,
        0xB4,
        0xA8,
        0x75,
        0xC8,
        0x20,
        0x34,
        0xBF,
        0x04,
        0x10,
        0x75,
        0x8C,
        0xB7,
        0x6D,
        0x49,
        0xDE,
        0x3D,
        0x3C,
        0x66,
        0x08,
        0xFE,
        0x67,
        0xC8,
        0x77,
        0x04,
        0x7C,
        0xA5,
        0xF0,
        0x9E,
        0xE7,
        0x5E,
        0x70,
        0xBF,
        0xDE,
        0xF1,
        0xCB,
        0x1C,
        0xC0,
        0x84,
        0x4A,
        0x89,
        0x76,
        0x37,
        0x4F,
        0xAD,
        0x3B,
        0x8F,
        0x04,
        0x91,
        0xD0,
        0x1B,
        0x0B,
        0xA8,
        0x20,
        0x6E,
        0x1E,
        0x97,
        0x1E,
        0xFF,
        0x1F,
        0xEF,
        0xDE,
        0x7A,
        0xD7,
        0x93,
        0x3C,
        0xA9,
        0x46,
        0xE5,
        0x74,
        0x66,
        0x9C,
        0x85,
        0xFA,
        0xAA,
        0x4A,
        0xE4,
        0x39,
        0xC5,
        0x33,
        0xBB,
        0x8E,
        0xCA,
        0x1F,
        0xD9,
        0x4C,
        0xBC,
        0xCD,
        0x7C,
        0xA1,
        0x30,
        0xDB,
        0x15,
        0xED,
        0xA1,
        0x24,
        0x9D,
        0xCB,
        0xF0,
        0xBE,
        0xEB,
        0x92,
        0x60,
        0xB0,
        0xAB,
        0x60,
        0xA0,
        0xCC,
        0xD8,
        0x04,
        0xF9,
        0xF1,
        0xA0,
        0x04,
        0x98,
        0x6A,
        0x20,
        0xD8,
        0x86,
        0xFF,
        0xD4,
        0x9D,
        0x09,
        0xA1,
        0x22,
        0xCE,
        0x0A,
        0x3E,
        0x21,
        0x27,
        0xCD,
        0xF8,
        0x7C,
        0xB0,
        0x09,
        0x09,
        0xC2,
        0xA3,
        0xCC,
    ]
)

TGL_INTEL_PROD_KEY = bytes(
    [
        0xD3,
        0x72,
        0x92,
        0x99,
        0x4E,
        0xB9,
        0xCD,
        0x67,
        0x41,
        0x86,
        0x16,
        0x77,
        0x35,
        0xA1,
        0x34,
        0x85,
        0x43,
        0x96,
        0xD9,
        0x53,
        0x76,
        0x4D,
        0xD0,
        0x63,
        0x17,
        0x72,
        0x96,
        0xEE,
        0xF6,
        0xDC,
        0x50,
        0x53,
        0x4B,
        0x4,
        0xAA,
        0xFE,
        0x3D,
        0xD7,
        0x21,
        0x29,
        0x79,
        0x6,
        0x76,
        0xEE,
        0xB3,
        0x70,
        0x23,
        0x8,
        0x26,
        0xA8,
        0x83,
        0x3D,
        0x70,
        0x13,
        0x9D,
        0x65,
        0xCB,
        0xD5,
        0xC6,
        0xF,
        0x92,
        0x93,
        0x38,
        0x29,
        0x19,
        0xA6,
        0x7C,
        0xBF,
        0xF1,
        0x76,
        0x75,
        0x2,
        0x9E,
        0x32,
        0x8F,
        0x1F,
        0x5,
        0xA6,
        0x2D,
        0x89,
        0x6D,
        0x38,
        0xBA,
        0x38,
        0xD,
        0xF1,
        0xE9,
        0xE8,
        0xED,
        0xF7,
        0x6C,
        0x20,
        0x8D,
        0x91,
        0xC,
        0xF8,
        0xDD,
        0x9A,
        0x56,
        0xD3,
        0xF7,
        0xBF,
        0x3C,
        0xDA,
        0xC8,
        0x5D,
        0xB,
        0xEF,
        0x20,
        0x5A,
        0xC1,
        0x5F,
        0x91,
        0x94,
        0xEE,
        0x90,
        0xB8,
        0xFC,
        0x2C,
        0x31,
        0x75,
        0xC3,
        0x7E,
        0x86,
        0xF6,
        0x4F,
        0x45,
        0x4C,
        0x64,
        0xE1,
        0xE9,
        0xE5,
        0xCD,
        0xF0,
        0xEC,
        0xEF,
        0xA7,
        0xBD,
        0x31,
        0x62,
        0x40,
        0xA8,
        0x48,
        0x52,
        0xD5,
        0x23,
        0xCE,
        0x4,
        0x45,
        0x2F,
        0xB,
        0x3D,
        0xE0,
        0x7A,
        0xCF,
        0xE5,
        0x2A,
        0x45,
        0x5E,
        0x91,
        0x1D,
        0x41,
        0xA7,
        0x40,
        0x85,
        0x34,
        0xE,
        0x50,
        0x45,
        0x59,
        0xBF,
        0xD,
        0xA6,
        0x6,
        0xF9,
        0xF6,
        0xCE,
        0xA2,
        0x76,
        0x72,
        0x0,
        0x62,
        0x73,
        0x37,
        0x1A,
        0xBE,
        0xD2,
        0xE3,
        0x1B,
        0x7B,
        0x26,
        0x7B,
        0x32,
        0xAA,
        0x79,
        0xED,
        0x59,
        0x23,
        0xB6,
        0xDB,
        0x9F,
        0x3C,
        0x3D,
        0x65,
        0xF3,
        0xBB,
        0x4B,
        0xB4,
        0x97,
        0xAA,
        0x2A,
        0xAE,
        0x48,
        0xF4,
        0xC5,
        0x59,
        0x8D,
        0x82,
        0x4A,
        0xB,
        0x15,
        0x4D,
        0xD5,
        0x4,
        0xA6,
        0xC1,
        0x2D,
        0x83,
        0x19,
        0xC4,
        0xC6,
        0x49,
        0xBA,
        0x0,
        0x1B,
        0x2B,
        0x70,
        0xB,
        0x26,
        0x7C,
        0xB8,
        0x94,
        0x18,
        0xE4,
        0x9A,
        0xF6,
        0x5A,
        0x68,
        0x9D,
        0x44,
        0xD2,
        0xED,
        0xD5,
        0x67,
        0x42,
        0x47,
        0x5F,
        0x73,
        0xC5,
        0xA7,
        0xE5,
        0x87,
        0xA9,
        0x4D,
        0xAE,
        0xC1,
        0xB,
        0x2C,
        0x46,
        0x16,
        0xD7,
        0x4E,
        0xF0,
        0xDC,
        0x61,
        0x58,
        0x51,
        0xB1,
        0x2,
        0xBC,
        0xCA,
        0x17,
        0xB1,
        0x1A,
        0xA,
        0x96,
        0x3B,
        0x25,
        0x1C,
        0x63,
        0x56,
        0x65,
        0x20,
        0x6E,
        0x1B,
        0x21,
        0xB1,
        0x94,
        0x7A,
        0xF5,
        0xBF,
        0x83,
        0x21,
        0x86,
        0x38,
        0xF1,
        0x66,
        0x1A,
        0xA,
        0x75,
        0x73,
        0xA,
        0xE,
        0xC7,
        0x64,
        0x68,
        0xC7,
        0xF9,
        0xC3,
        0x4A,
        0x73,
        0xFB,
        0x86,
        0xA5,
        0x7,
        0xB8,
        0x8B,
        0xF0,
        0xA3,
        0x3B,
        0xA9,
        0x8F,
        0x33,
        0xA7,
        0xCE,
        0xFE,
        0x36,
        0x60,
        0xBD,
        0x5,
        0xF0,
        0x9A,
        0x30,
        0xE5,
        0xE1,
        0x43,
        0x25,
        0x1C,
        0x1,
        0x4A,
        0xD4,
        0x23,
        0x1E,
        0x8F,
        0xB9,
        0xDD,
        0xD8,
        0xB2,
        0x24,
        0xEF,
        0x36,
        0x4D,
        0x5B,
        0x8F,
        0xBA,
        0x4F,
        0xE9,
        0x48,
        0xE7,
        0x51,
        0x42,
        0x59,
        0x56,
        0xA,
        0x1C,
        0xF,
        0x5D,
        0x62,
        0x4A,
        0x80,
        0x96,
        0x31,
        0xF8,
        0xB5,
    ]
)

EHL_INTEL_PROD_KEY = bytes(
    [
        0xB5,
        0xB0,
        0xE2,
        0x25,
        0x3D,
        0xC7,
        0x54,
        0x10,
        0xDE,
        0x3C,
        0xC9,
        0x24,
        0x97,
        0x74,
        0xBC,
        0x02,
        0x7D,
        0x0B,
        0xD6,
        0x61,
        0x2E,
        0x35,
        0x65,
        0xED,
        0x78,
        0xF6,
        0x85,
        0x73,
        0x1F,
        0x8C,
        0xDA,
        0x8F,
        0x50,
        0x79,
        0xC7,
        0x0C,
        0x9E,
        0xB4,
        0x09,
        0x3B,
        0xFC,
        0x2E,
        0x4E,
        0xF3,
        0x46,
        0xFE,
        0x3F,
        0x20,
        0x9D,
        0x8D,
        0xF6,
        0x3E,
        0xC3,
        0x46,
        0x92,
        0xF9,
        0xCE,
        0xBB,
        0x7D,
        0x0B,
        0xB3,
        0x45,
        0x35,
        0x76,
        0xBE,
        0x19,
        0x87,
        0x21,
        0x6C,
        0x79,
        0xFA,
        0xF4,
        0xC8,
        0x8E,
        0x07,
        0x26,
        0x03,
        0x0D,
        0xE9,
        0xE3,
        0x1E,
        0x61,
        0x7C,
        0xD1,
        0x45,
        0x10,
        0x61,
        0x1C,
        0x79,
        0x3F,
        0x10,
        0xA9,
        0x42,
        0x60,
        0x2C,
        0x7A,
        0x7A,
        0x89,
        0x1B,
        0x54,
        0xDA,
        0x0E,
        0x54,
        0x08,
        0x30,
        0x0F,
        0x6E,
        0x37,
        0xEA,
        0xB7,
        0x58,
        0xA0,
        0xAF,
        0x4A,
        0x94,
        0x2C,
        0x43,
        0x50,
        0x74,
        0xED,
        0x16,
        0xDC,
        0x11,
        0xA1,
        0xD3,
        0x6E,
        0x54,
        0xA6,
        0x56,
        0xF9,
        0x40,
        0x8C,
        0x3F,
        0xA3,
        0x74,
        0xAE,
        0x4F,
        0x48,
        0xC8,
        0x79,
        0x30,
        0x5A,
        0x99,
        0x79,
        0x26,
        0xE1,
        0x52,
        0x9B,
        0xFE,
        0x9E,
        0xAF,
        0x96,
        0xCC,
        0xE6,
        0x9A,
        0x53,
        0x2E,
        0xE4,
        0x40,
        0xCC,
        0xAD,
        0x19,
        0x8E,
        0x23,
        0x53,
        0x63,
        0xC8,
        0xFD,
        0x96,
        0xEB,
        0x27,
        0x9B,
        0x3E,
        0x49,
        0x0D,
        0x90,
        0xB0,
        0x67,
        0xB4,
        0x05,
        0x4A,
        0x55,
        0x5B,
        0xB0,
        0xA5,
        0x68,
        0xB8,
        0x60,
        0xA4,
        0x81,
        0x6A,
        0x3E,
        0x8C,
        0xBC,
        0x29,
        0xCD,
        0x85,
        0x45,
        0x3C,
        0xF4,
        0x86,
        0xF8,
        0x9B,
        0x69,
        0xB5,
        0xC5,
        0xB9,
        0xAA,
        0xC8,
        0xED,
        0x7D,
        0x70,
        0x45,
        0xB6,
        0xF6,
        0x5B,
        0x48,
        0x62,
        0xF6,
        0x68,
        0xE8,
        0xDD,
        0x79,
        0xDA,
        0xB0,
        0xE9,
        0x3C,
        0x8F,
        0x01,
        0x92,
        0x80,
        0x73,
        0x89,
        0x7D,
        0x9A,
        0xAF,
        0x31,
        0x85,
        0x75,
        0x7C,
        0x89,
        0xF3,
        0x6C,
        0x77,
        0x95,
        0x5B,
        0xA9,
        0xC5,
        0xE1,
        0x33,
        0xE0,
        0x44,
        0x81,
        0x7E,
        0x72,
        0xA5,
        0xBB,
        0x3D,
        0x40,
        0xB7,
        0xC9,
        0x77,
        0xD8,
        0xC3,
        0xE3,
        0xEF,
        0x42,
        0xAE,
        0x57,
        0x91,
        0x63,
        0x0C,
        0x26,
        0xAC,
        0x5E,
        0x10,
        0x51,
        0x28,
        0xE6,
        0x61,
        0xAD,
        0x4D,
        0xC4,
        0x93,
        0xB2,
        0xE0,
        0xB4,
        0x31,
        0x60,
        0x5A,
        0x97,
        0x0E,
        0x80,
        0x86,
        0x91,
        0xC9,
        0xCD,
        0xFC,
        0x97,
        0xC3,
        0x78,
        0xBD,
        0xCA,
        0xCE,
        0xD3,
        0x96,
        0xEE,
        0x75,
        0x81,
        0xE0,
        0x8B,
        0x45,
        0x8E,
        0x20,
        0x4B,
        0x98,
        0x31,
        0x0F,
        0xF9,
        0x66,
        0xB3,
        0x04,
        0xB7,
        0x0D,
        0xDE,
        0x68,
        0x1E,
        0x2A,
        0xE4,
        0xEC,
        0x45,
        0x2A,
        0x0A,
        0x24,
        0x81,
        0x82,
        0xCB,
        0x86,
        0xA0,
        0x61,
        0x7F,
        0xE7,
        0x96,
        0x84,
        0x4B,
        0x30,
        0xC4,
        0x7D,
        0x5C,
        0x1B,
        0x2C,
        0x1E,
        0x66,
        0x68,
        0x71,
        0x1D,
        0x39,
        0x6C,
        0x23,
        0x07,
        0x6D,
        0xF3,
        0x3E,
        0x64,
        0xC3,
        0x03,
        0x97,
        0x84,
        0x14,
        0xD1,
        0xF6,
        0x50,
        0xF4,
        0x32,
        0x5D,
        0xAE,
        0xAD,
        0x23,
        0x46,
        0x0C,
        0x9F,
        0xFC,
        0x3E,
        0xB9,
    ]
)

ADL_INTEL_PROD_KEY = bytes(
    [
        0xD3,
        0x42,
        0x11,
        0x78,
        0xF4,
        0x4A,
        0xA5,
        0x85,
        0x4B,
        0x78,
        0x7A,
        0x9B,
        0xBD,
        0x71,
        0xC1,
        0x84,
        0x0F,
        0x54,
        0xE4,
        0x07,
        0x47,
        0x65,
        0x9E,
        0xDC,
        0x79,
        0x85,
        0x14,
        0x52,
        0x3C,
        0xA1,
        0xE1,
        0x06,
        0x4C,
        0x25,
        0x31,
        0x56,
        0xB2,
        0xBA,
        0x7C,
        0xFD,
        0x3D,
        0x2D,
        0x87,
        0x28,
        0xF4,
        0xB3,
        0x19,
        0xE9,
        0x38,
        0xD9,
        0x78,
        0x3C,
        0x45,
        0x7D,
        0xFA,
        0x9C,
        0x58,
        0x3A,
        0xAF,
        0xDA,
        0x4B,
        0xE1,
        0x94,
        0xCC,
        0xB0,
        0xDB,
        0x41,
        0x5D,
        0x5F,
        0xD5,
        0xF9,
        0xEB,
        0x53,
        0xCC,
        0xD7,
        0x14,
        0xAB,
        0xDB,
        0x13,
        0x20,
        0x26,
        0x59,
        0xC0,
        0x7E,
        0xAA,
        0x14,
        0x7F,
        0x80,
        0x0F,
        0x73,
        0x9A,
        0xB2,
        0xC4,
        0x8C,
        0x8B,
        0x0D,
        0x56,
        0xD0,
        0x7A,
        0xD1,
        0x52,
        0xCA,
        0xAA,
        0x96,
        0x28,
        0x8E,
        0x98,
        0xAD,
        0x6E,
        0xF6,
        0x36,
        0x1A,
        0x6E,
        0xDD,
        0xBA,
        0x4F,
        0xD5,
        0xB1,
        0x06,
        0xE6,
        0xC8,
        0x5A,
        0x06,
        0x93,
        0x06,
        0x51,
        0xD1,
        0x44,
        0xE1,
        0x87,
        0x54,
        0x49,
        0x2F,
        0xFD,
        0xA5,
        0x2B,
        0x86,
        0xBE,
        0xEA,
        0x59,
        0xA9,
        0x09,
        0xF5,
        0x1F,
        0x01,
        0xA4,
        0x7A,
        0x0B,
        0xD9,
        0xD0,
        0x73,
        0x13,
        0x1A,
        0x4A,
        0xB3,
        0xD5,
        0x4D,
        0x37,
        0x06,
        0x6B,
        0x84,
        0x48,
        0xCE,
        0xBB,
        0x0B,
        0x81,
        0x71,
        0xA1,
        0x97,
        0x3F,
        0x95,
        0x64,
        0x6B,
        0xFD,
        0xB0,
        0x37,
        0x4E,
        0xFD,
        0xA5,
        0x0B,
        0x08,
        0xB3,
        0xD0,
        0xBC,
        0xBE,
        0x27,
        0x64,
        0x72,
        0x89,
        0xC7,
        0xC8,
        0x58,
        0x7E,
        0x83,
        0x8A,
        0x0F,
        0xF5,
        0x56,
        0xA7,
        0x53,
        0x06,
        0x24,
        0xA1,
        0x9E,
        0x2C,
        0xD2,
        0x35,
        0x86,
        0xDF,
        0x6D,
        0x68,
        0xDD,
        0x7A,
        0x95,
        0xBF,
        0xF5,
        0x7A,
        0xA4,
        0x52,
        0xF9,
        0xC2,
        0x03,
        0xA8,
        0xA1,
        0x63,
        0x38,
        0x1E,
        0xC9,
        0x2B,
        0x1D,
        0xCB,
        0x55,
        0x04,
        0x4B,
        0xED,
        0x53,
        0x06,
        0xB4,
        0x96,
        0xC8,
        0x84,
        0x73,
        0x66,
        0x66,
        0xBE,
        0xB9,
        0xCA,
        0xFC,
        0x8B,
        0x81,
        0xE2,
        0xBD,
        0x0B,
        0x8E,
        0xA3,
        0x93,
        0x98,
        0x82,
        0x1D,
        0x8E,
        0x99,
        0xF7,
        0x29,
        0x48,
        0x3D,
        0xEB,
        0x70,
        0xDA,
        0x02,
        0x6E,
        0x2E,
        0xC7,
        0x6C,
        0x60,
        0x7C,
        0x3D,
        0xFF,
        0x78,
        0xDC,
        0x95,
        0x4B,
        0xEC,
        0x89,
        0x7A,
        0x97,
        0x61,
        0x32,
        0x7E,
        0x00,
        0x59,
        0x1D,
        0x1D,
        0xBE,
        0x3A,
        0x55,
        0xB8,
        0x2E,
        0xA1,
        0xB4,
        0xF8,
        0x6C,
        0xAD,
        0x92,
        0xBC,
        0x47,
        0x27,
        0xE8,
        0x0E,
        0xAD,
        0x80,
        0xCA,
        0xCA,
        0xB2,
        0x92,
        0x71,
        0xAA,
        0x19,
        0x2B,
        0x3A,
        0x4E,
        0xBB,
        0x01,
        0x76,
        0x9B,
        0x6D,
        0x42,
        0xD3,
        0xC4,
        0x2F,
        0x29,
        0x8F,
        0x3F,
        0xD2,
        0xD1,
        0xD9,
        0xCB,
        0x48,
        0xB3,
        0x99,
        0xCE,
        0x78,
        0xFA,
        0x29,
        0x69,
        0xDC,
        0x55,
        0xDE,
        0xCF,
        0xC0,
        0xC9,
        0x2F,
        0xBE,
        0x67,
        0x22,
        0xB4,
        0x02,
        0x38,
        0x18,
        0xBD,
        0xA6,
        0x98,
        0xCF,
        0xC9,
        0x42,
        0x8E,
        0xDD,
        0xBD,
        0xA0,
        0xCC,
        0x17,
        0xB2,
        0x12,
        0xD3,
        0x32,
        0x0F,
        0x1E,
        0x0C,
        0x8E,
        0x94,
        0x8B,
        0x7C,
        0xBE,
        0x79,
        0xEB,
    ]
)

ADL_N_INTEL_PROD_KEY = bytes(
    [
        0xE1,
        0x71,
        0x6A,
        0xED,
        0xFA,
        0x0B,
        0x75,
        0xB3,
        0xD3,
        0x1A,
        0x7B,
        0xD9,
        0xB8,
        0x56,
        0x43,
        0x90,
        0x81,
        0x9E,
        0x6E,
        0x4F,
        0xB6,
        0x94,
        0xA2,
        0x44,
        0x3C,
        0xD7,
        0x80,
        0x98,
        0x54,
        0x48,
        0xA2,
        0xBB,
        0x4A,
        0xD2,
        0xEB,
        0x25,
        0x8D,
        0x5B,
        0x5C,
        0x18,
        0x5D,
        0x0C,
        0xA8,
        0x87,
        0xB7,
        0xB7,
        0xEC,
        0xEB,
        0x49,
        0xF9,
        0x03,
        0x14,
        0x81,
        0x13,
        0x11,
        0xE0,
        0xBB,
        0x41,
        0x84,
        0x93,
        0xA1,
        0x09,
        0x2E,
        0xBF,
        0xA3,
        0xE6,
        0xC5,
        0x80,
        0x76,
        0x86,
        0x08,
        0xF3,
        0x37,
        0x21,
        0xD6,
        0xCE,
        0x7E,
        0xF2,
        0x47,
        0x31,
        0xD0,
        0x07,
        0x6C,
        0x98,
        0x15,
        0x1F,
        0x93,
        0x07,
        0x31,
        0x57,
        0xC6,
        0x90,
        0x53,
        0xCF,
        0x27,
        0x2D,
        0x01,
        0x89,
        0x22,
        0xC0,
        0xE0,
        0x00,
        0x86,
        0xF8,
        0x8C,
        0x58,
        0x94,
        0x97,
        0x2C,
        0x09,
        0x6A,
        0x26,
        0xDA,
        0x6B,
        0x0D,
        0x1D,
        0xCD,
        0x8E,
        0x7F,
        0x0B,
        0xED,
        0xAF,
        0xEB,
        0x14,
        0x79,
        0x8C,
        0x1F,
        0xEC,
        0xE4,
        0xC6,
        0xD2,
        0x39,
        0x20,
        0x26,
        0x2B,
        0xEC,
        0xF3,
        0x07,
        0x89,
        0xFD,
        0x13,
        0x6F,
        0xA7,
        0x58,
        0xE0,
        0xA9,
        0xB2,
        0xAA,
        0xAB,
        0x7F,
        0x87,
        0xFD,
        0x7C,
        0xCB,
        0x92,
        0xC0,
        0x54,
        0x06,
        0x46,
        0xEF,
        0xB0,
        0xAB,
        0xFC,
        0x52,
        0xD7,
        0x18,
        0x82,
        0x18,
        0xA2,
        0x4A,
        0xA6,
        0xE8,
        0xF6,
        0x1E,
        0xBE,
        0xCD,
        0xF3,
        0x94,
        0x4F,
        0xD8,
        0xD8,
        0x94,
        0xA8,
        0x26,
        0xB2,
        0x25,
        0x28,
        0x12,
        0x33,
        0x07,
        0x69,
        0xF5,
        0x55,
        0x2C,
        0xCD,
        0x94,
        0x83,
        0x42,
        0xE3,
        0x4E,
        0xF2,
        0xE8,
        0x49,
        0x0A,
        0x40,
        0xE9,
        0x03,
        0x1A,
        0x05,
        0x34,
        0x45,
        0xAB,
        0x82,
        0x1F,
        0xAD,
        0x0D,
        0x5D,
        0x24,
        0x08,
        0x25,
        0x49,
        0x7D,
        0xAA,
        0x06,
        0x30,
        0x3E,
        0x25,
        0xF4,
        0x47,
        0x94,
        0xBA,
        0x20,
        0xD2,
        0xC2,
        0x1D,
        0x20,
        0x83,
        0x3F,
        0xB1,
        0xC7,
        0x9C,
        0x69,
        0x05,
        0x82,
        0xF4,
        0x9E,
        0x70,
        0x8E,
        0x06,
        0x67,
        0x9D,
        0xE2,
        0x8A,
        0x25,
        0x86,
        0x95,
        0xAF,
        0xE0,
        0x41,
        0x56,
        0x68,
        0x84,
        0xA5,
        0x91,
        0xDB,
        0x8E,
        0xC6,
        0xA7,
        0xD6,
        0xCB,
        0xB3,
        0x1F,
        0x46,
        0x53,
        0xE5,
        0x52,
        0x4D,
        0xB7,
        0x3F,
        0x0D,
        0x98,
        0x13,
        0x80,
        0xC0,
        0xD5,
        0x9F,
        0x21,
        0x55,
        0xCF,
        0x38,
        0x1E,
        0xCF,
        0x4F,
        0x58,
        0xF7,
        0x68,
        0x98,
        0xDA,
        0x15,
        0xD4,
        0x54,
        0x89,
        0xEA,
        0xDF,
        0x52,
        0x98,
        0x97,
        0x92,
        0xD8,
        0xCC,
        0x4B,
        0xDC,
        0xF7,
        0x1B,
        0xC4,
        0xE5,
        0xDB,
        0x5D,
        0xE7,
        0xAE,
        0x9E,
        0x00,
        0x77,
        0x32,
        0x4C,
        0x5F,
        0x3B,
        0x11,
        0xA0,
        0xCF,
        0xBE,
        0xC3,
        0xE6,
        0x84,
        0xD8,
        0xA6,
        0x58,
        0x36,
        0x90,
        0xBC,
        0xC5,
        0x98,
        0xDC,
        0xFF,
        0x48,
        0x2F,
        0xE7,
        0xDD,
        0x26,
        0xA6,
        0x4D,
        0x15,
        0xE6,
        0x39,
        0x7E,
        0x41,
        0xD2,
        0x7D,
        0xB6,
        0x8F,
        0xF8,
        0xEC,
        0x54,
        0xB0,
        0xEC,
        0xAD,
        0x0C,
        0x30,
        0x7B,
        0x6F,
        0x9C,
        0x5A,
        0xE1,
        0x92,
        0xF7,
        0x48,
        0x63,
        0x32,
        0xAD,
        0xAD,
        0xE3,
        0x34,
        0x59,
        0xCC,
    ]
)

COMMUNITY_KEY = bytes(
    [
        0x85,
        0x00,
        0xE1,
        0x68,
        0xAA,
        0xEB,
        0xD2,
        0x07,
        0x1B,
        0x7C,
        0x5E,
        0xED,
        0xD6,
        0xE7,
        0xE5,
        0xF9,
        0xC1,
        0x0E,
        0x47,
        0xD4,
        0x4C,
        0xAB,
        0x8C,
        0xF0,
        0xE8,
        0xEE,
        0x8B,
        0x40,
        0x36,
        0x35,
        0x58,
        0x8F,
        0xF4,
        0x6F,
        0xFC,
        0xFD,
        0x0F,
        0xDD,
        0x55,
        0x8B,
        0x45,
        0x8C,
        0xF0,
        0x47,
        0xDC,
        0xB4,
        0xAC,
        0x21,
        0x3B,
        0x4B,
        0x20,
        0xE6,
        0x81,
        0xB3,
        0xCC,
        0x90,
        0xD4,
        0x5E,
        0xF1,
        0xA4,
        0x9B,
        0x68,
        0x52,
        0xC8,
        0xF1,
        0x2D,
        0xF9,
        0xC4,
        0x77,
        0xC6,
        0x4D,
        0xA9,
        0x90,
        0xC7,
        0x10,
        0xFD,
        0x43,
        0xC8,
        0x4B,
        0x6B,
        0x23,
        0x5E,
        0x92,
        0xF5,
        0x8F,
        0xAC,
        0xD5,
        0x7D,
        0x60,
        0x27,
        0x36,
        0x7C,
        0x21,
        0x4E,
        0x21,
        0x99,
        0xDE,
        0xCB,
        0xC0,
        0x45,
        0xF3,
        0x04,
        0x22,
        0xB8,
        0x7D,
        0x16,
        0x68,
        0x40,
        0xF9,
        0x5C,
        0xF0,
        0xB9,
        0x7E,
        0x8C,
        0x05,
        0xB6,
        0xFC,
        0x28,
        0xBB,
        0x3D,
        0xD8,
        0xFF,
        0xB6,
        0xA4,
        0xD4,
        0x54,
        0x27,
        0x3B,
        0x1A,
        0x42,
        0x4E,
        0xF5,
        0xA6,
        0xA8,
        0x5E,
        0x44,
        0xE2,
        0x9E,
        0xED,
        0x68,
        0x6A,
        0x27,
        0x60,
        0x13,
        0x8D,
        0x2F,
        0x27,
        0x70,
        0xCD,
        0x57,
        0xC9,
        0x18,
        0xA3,
        0xB0,
        0x30,
        0xA1,
        0xF4,
        0xE6,
        0x32,
        0x12,
        0x89,
        0x2A,
        0xAF,
        0x40,
        0xA5,
        0xFD,
        0x52,
        0xF1,
        0xAA,
        0x8A,
        0xA4,
        0xEF,
        0x20,
        0x3D,
        0x10,
        0xA3,
        0x70,
        0xF2,
        0x39,
        0xC5,
        0x05,
        0x99,
        0x22,
        0x10,
        0x81,
        0x83,
        0x6E,
        0x45,
        0xA4,
        0xF3,
        0x5A,
        0x9D,
        0x6A,
        0xB8,
        0x88,
        0xFE,
        0x69,
        0x40,
        0xD1,
        0xB1,
        0xCB,
        0x2A,
        0xDB,
        0x28,
        0x05,
        0xDE,
        0x54,
        0xBF,
        0x3D,
        0x86,
        0x5F,
        0x39,
        0x8B,
        0xC1,
        0xF4,
        0xAF,
        0x00,
        0x61,
        0x86,
        0x01,
        0xFA,
        0x22,
        0xAC,
        0xF6,
        0x2C,
        0xA4,
        0x17,
        0x6A,
        0xA7,
        0xD8,
        0x0A,
        0x8C,
        0x9F,
        0xBF,
        0x1F,
        0x62,
        0xB2,
        0x2E,
        0x68,
        0x52,
        0x3F,
        0x82,
        0x8F,
        0xE5,
        0x28,
        0x4D,
        0xDB,
        0xB5,
        0x5A,
        0x96,
        0x28,
        0x27,
        0x19,
        0xAF,
        0x43,
        0xB9,
    ]
)

COMMUNITY_KEY2 = bytes(
    [
        0x6B,
        0x75,
        0xED,
        0x58,
        0x20,
        0x08,
        0x85,
        0x95,
        0xA0,
        0x49,
        0x8B,
        0x9E,
        0xBD,
        0x5F,
        0x34,
        0x82,
        0x0A,
        0x9D,
        0x1E,
        0x9A,
        0xB6,
        0x76,
        0x43,
        0x19,
        0xB7,
        0x76,
        0x45,
        0x5B,
        0x59,
        0xAB,
        0xBB,
        0xF3,
        0x9E,
        0x72,
        0xF2,
        0x41,
        0x24,
        0x92,
        0x97,
        0xEF,
        0x39,
        0xC0,
        0xED,
        0xC4,
        0x7A,
        0x4E,
        0xDB,
        0xEC,
        0xEB,
        0xC7,
        0x4C,
        0xF6,
        0x45,
        0xBE,
        0xB2,
        0xE0,
        0x13,
        0x6A,
        0xDC,
        0x06,
        0x7A,
        0x1C,
        0xBD,
        0x8D,
        0xD8,
        0xD2,
        0xD7,
        0x82,
        0x6D,
        0xBE,
        0x03,
        0x76,
        0x3B,
        0x6B,
        0xB8,
        0x2F,
        0xCC,
        0xBE,
        0x30,
        0x56,
        0x61,
        0x87,
        0x09,
        0xDF,
        0x44,
        0x51,
        0xF8,
        0x82,
        0xC5,
        0x78,
        0x05,
        0x45,
        0x8C,
        0xE3,
        0x78,
        0x0E,
        0xD3,
        0x7A,
        0xD4,
        0xF4,
        0xBE,
        0x96,
        0xDE,
        0xB8,
        0x3B,
        0x78,
        0x90,
        0x8B,
        0xD3,
        0xDD,
        0x0B,
        0xDD,
        0xBE,
        0x56,
        0xF3,
        0x9A,
        0x34,
        0xC9,
        0x38,
        0x47,
        0x8D,
        0xC4,
        0xBD,
        0x5E,
        0x68,
        0xF8,
        0x62,
        0xC4,
        0x28,
        0xDD,
        0x00,
        0x48,
        0x93,
        0xB5,
        0xAD,
        0x74,
        0x52,
        0xE5,
        0xF3,
        0xD2,
        0x97,
        0xDE,
        0xBC,
        0x0A,
        0x85,
        0x95,
        0xE9,
        0xFA,
        0xD2,
        0xAC,
        0xDC,
        0xDC,
        0x59,
        0x74,
        0xFA,
        0x57,
        0xF2,
        0xD3,
        0x61,
        0xC6,
        0x2B,
        0x26,
        0xDE,
        0x57,
        0x50,
        0xE2,
        0x58,
        0x6B,
        0x79,
        0x65,
        0x0B,
        0x49,
        0x2C,
        0x59,
        0x28,
        0x25,
        0x64,
        0x31,
        0x93,
        0x65,
        0x9A,
        0x0A,
        0x88,
        0x98,
        0x9A,
        0x77,
        0x00,
        0x47,
        0x8F,
        0xA0,
        0xC7,
        0x6B,
        0x58,
        0x90,
        0xA9,
        0xB5,
        0x15,
        0xFF,
        0x65,
        0x7C,
        0x84,
        0x02,
        0xD4,
        0xDD,
        0x09,
        0xF1,
        0x25,
        0xAD,
        0xF9,
        0x30,
        0xAA,
        0x34,
        0x5B,
        0x77,
        0xEF,
        0xB2,
        0x75,
        0x3D,
        0x54,
        0x9D,
        0xCC,
        0x0D,
        0x11,
        0xDA,
        0x91,
        0x01,
        0x2E,
        0x51,
        0xDC,
        0x0C,
        0x8A,
        0x92,
        0x71,
        0x44,
        0x9A,
        0xD5,
        0x69,
        0x5D,
        0x7A,
        0xAD,
        0xAF,
        0xDF,
        0x25,
        0xEA,
        0x95,
        0x21,
        0xBB,
        0x99,
        0x53,
        0x89,
        0xBC,
        0x54,
        0xCA,
        0xF3,
        0x54,
        0xF5,
        0xBB,
        0x38,
        0x27,
        0x64,
        0xCE,
        0xF2,
        0x17,
        0x25,
        0x75,
        0x33,
        0x1A,
        0x2D,
        0x19,
        0x00,
        0xFF,
        0x9B,
        0xD9,
        0x4D,
        0x0C,
        0xB1,
        0xA5,
        0x55,
        0x55,
        0xA9,
        0x29,
        0x8E,
        0xFB,
        0x82,
        0x43,
        0xEB,
        0xFA,
        0xC8,
        0x33,
        0x76,
        0xF3,
        0x7D,
        0xEE,
        0x95,
        0xE1,
        0x39,
        0xBA,
        0xA5,
        0x4A,
        0xD5,
        0xB1,
        0x8A,
        0xA6,
        0xFF,
        0x8F,
        0x4B,
        0x45,
        0x8C,
        0xE9,
        0x7B,
        0x87,
        0xAE,
        0x8D,
        0x32,
        0x6E,
        0x16,
        0xE7,
        0x9E,
        0x85,
        0x22,
        0x71,
        0x3D,
        0x17,
        0xBA,
        0x54,
        0xED,
        0x73,
        0x87,
        0xE5,
        0x9D,
        0xBF,
        0xC0,
        0xCD,
        0x76,
        0xFA,
        0x83,
        0xD4,
        0xC5,
        0x30,
        0xD1,
        0xC7,
        0x25,
        0x49,
        0x25,
        0x75,
        0x4D,
        0x0A,
        0x4A,
        0x2D,
        0x13,
        0x1C,
        0x12,
        0x2E,
        0x5D,
        0x2A,
        0xE2,
        0xA9,
        0xAE,
        0xBF,
        0x8F,
        0xDF,
        0x24,
        0x76,
        0xF5,
        0x81,
        0x1E,
        0x09,
        0x5D,
        0x63,
        0x04,
        0xAF,
        0x24,
        0x45,
        0x87,
        0xF4,
        0x96,
        0x55,
        0xD1,
        0x7D,
        0xC6,
        0x0D,
        0x79,
        0x12,
        0xA9,
    ]
)

KNOWN_KEYS = {
    APL_INTEL_PROD_KEY: "APL Intel prod key",
    CNL_INTEL_PROD_KEY: "CNL Intel prod key",
    ICL_INTEL_PROD_KEY: "ICL Intel prod key",
    JSL_INTEL_PROD_KEY: "JSL Intel prod key",
    TGL_INTEL_PROD_KEY: "TGL Intel prod key",
    EHL_INTEL_PROD_KEY: "EHL Intel prod key",
    ADL_INTEL_PROD_KEY: "ADL Intel prod key",
    ADL_N_INTEL_PROD_KEY: "ADL-N Intel prod key",
    COMMUNITY_KEY: "Community key",
    COMMUNITY_KEY2: "Community 3k key",
}


def parse_params():
    """Parses parameters"""
    parser = argparse.ArgumentParser(description="SOF Binary Info Utility")
    parser.add_argument(
        "-v",
        "--verbose",
        help="increase output verbosity",
        action="store_true",
    )
    parser.add_argument(
        "--headers", help="display headers only", action="store_true"
    )
    parser.add_argument(
        "--full_bytes", help="display full byte arrays", action="store_true"
    )
    parser.add_argument(
        "--no_colors", help="disable colors in output", action="store_true"
    )
    parser.add_argument(
        "--no_cse", help="disable cse manifest parsing", action="store_true"
    )
    parser.add_argument(
        "--no_headers",
        help="skip information about headers",
        action="store_true",
    )
    parser.add_argument(
        "--no_modules",
        help="skip information about modules",
        action="store_true",
    )
    parser.add_argument(
        "--no_memory",
        help="skip information about memory",
        action="store_true",
    )
    parser.add_argument(
        "--valid",
        help="is ri signed by Intel production key",
        action="store_true",
    )
    parser.add_argument("sof_ri_path", help="path to fw binary file to parse")
    parsed_args = parser.parse_args()

    return parsed_args


# Helper Functions


def change_color(color):
    """Prints escape code to change text color"""
    color_code = {
        "red": 91,
        "green": 92,
        "yellow": 93,
        "blue": 94,
        "magenta": 95,
        "cyan": 96,
        "white": 98,
        "none": 0,
    }
    return "\033[{}m".format(color_code[color])


def uint_to_string(uint, both=False):
    """Prints uint in readable form"""
    if both:
        return hex(uint) + " (" + repr(uint) + ")"
    return hex(uint)


def date_to_string(date):
    """Prints BCD date in readable form"""
    return date[2:6] + "/" + date[6:8] + "/" + date[8:10]


def chararr_to_string(chararr, max_len):
    """Prints array of characters (null terminated or till max_len)
    in readable form
    """
    out = ""
    for i in range(0, max_len):
        if chararr[i] == 0:
            return out
        out += "{:c}".format(chararr[i])
    return out


def mod_type_to_string(mod_type):
    """Prints module type in readable form"""
    out = "("
    # type
    if (mod_type & 0xF) == 0:
        out += " builtin"
    elif (mod_type & 0xF) == 1:
        out += " loadable"
    # Module that may be instantiated by fw on startup
    if ((mod_type >> 4) & 0x1) == 1:
        out += " auto_start"
    # Module designed to run with low latency scheduler
    if ((mod_type >> 5) & 0x1) == 1:
        out += " LL"
    # Module designed to run with edf scheduler
    if ((mod_type >> 6) & 0x1) == 1:
        out += " DP"
    out += " )"
    return out


def seg_flags_to_string(flags):
    """Prints module segment flags in readable form"""
    out = "("
    if flags & 0x1 == 0x1:
        out = out + " contents"
    if flags & 0x2 == 0x2:
        out = out + " alloc"
    if flags & 0x4 == 0x4:
        out = out + " load"
    if flags & 0x8 == 0x8:
        out = out + " readonly"
    if flags & 0x10 == 0x10:
        out = out + " code"
    if flags & 0x20 == 0x20:
        out = out + " data"
    out = out + " type=" + repr((flags >> 8) & 0xF)
    out = out + " pages=" + repr((flags >> 16) & 0xFFFF)
    out = out + " )"
    return out


# Parsers


def parse_extended_manifest_ae1(reader):
    ext_mft = ExtendedManifestAE1()
    hdr = Component("ext_mft_hdr", "Header", 0)
    ext_mft.add_comp(hdr)

    sig = reader.read_string(4)
    reader.info("Extended Manifest (" + sig + ")", -4)
    hdr.add_a(Astring("sig", sig))

    # Next dword is the total length of the extended manifest
    # (need to use it for further parsing)
    reader.ext_mft_length = reader.read_dw()
    hdr.add_a(Auint("length", reader.ext_mft_length))
    hdr.add_a(Astring("ver", "{}.{}".format(reader.read_w(), reader.read_w())))
    hdr.add_a(Auint("entries", reader.read_dw()))

    reader.ff_data(reader.ext_mft_length - 16)
    return ext_mft


def parse_extended_manifest_xman(reader):
    ext_mft = ExtendedManifestXMan()
    hdr = Component("ext_mft_hdr", "Header", 0)
    ext_mft.add_comp(hdr)

    sig = reader.read_string(4)
    reader.info("Extended Manifest (" + sig + ")", -4)
    hdr.add_a(Astring("sig", sig))

    # Next dword is the total length of the extended manifest
    # (need to use it for further parsing)
    reader.ext_mft_length = reader.read_dw()
    hdr_length = reader.read_dw()
    hdr_ver = reader.read_dw()

    major = hdr_ver >> 24
    minor = (hdr_ver >> 12) & 0xFFF
    patch = hdr_ver & 0xFFF

    hdr.add_a(Auint("length", reader.ext_mft_length))
    hdr.add_a(Astring("ver", "{}.{}.{}".format(major, minor, patch)))
    hdr.add_a(Auint("hdr_length", hdr_length))

    reader.ff_data(reader.ext_mft_length - 16)
    return ext_mft


def parse_extended_manifest(reader):
    """Parses extended manifest from sof binary"""

    reader.info("Looking for Extended Manifest")
    # Try to detect signature first
    sig = reader.read_string(4)
    reader.set_offset(0)
    if sig == "$AE1":
        ext_mft = parse_extended_manifest_ae1(reader)
    elif sig == "XMan":
        ext_mft = parse_extended_manifest_xman(reader)
    else:
        ext_mft = ExtendedManifestAE1()
        hdr = Component("ext_mft_hdr", "Header", 0)
        ext_mft.add_comp(hdr)
        reader.info("info: Extended Manifest not found (sig = " + sig + ")")
        reader.ext_mft_length = 0
        hdr.add_a(Auint("length", reader.ext_mft_length))

    return ext_mft


def parse_cse_manifest(reader):
    """Parses CSE manifest form sof binary"""
    reader.info("Looking for CSE Manifest")
    cse_mft = CseManifest(reader.get_offset())

    # Try to detect signature first
    sig = reader.read_string(4)
    if sig != "$CPD":
        reader.error("CSE Manifest NOT found " + sig + ")", -4)
        sys.exit(1)
    reader.info("CSE Manifest (" + sig + ")", -4)

    # Read the header
    hdr = Component("cse_mft_hdr", "Header", reader.get_offset())
    cse_mft.add_comp(hdr)
    hdr.add_a(Astring("sig", sig))
    # read number of entries
    nb_entries = reader.read_dw()
    reader.info("# of entries {}".format(nb_entries))
    hdr.add_a(Adec("nb_entries", nb_entries))
    # read version (1byte for header ver and 1 byte for entry ver)
    ver = reader.read_w()
    hdr.add_a(Ahex("header_version", ver))
    header_length = reader.read_b()
    hdr.add_a(Ahex("header_length", header_length))
    hdr.add_a(Ahex("checksum", reader.read_b()))
    hdr.add_a(Astring("partition_name", reader.read_string(4)))

    reader.set_offset(cse_mft.file_offset + header_length)
    # Read entries
    nb_index = 0
    while nb_index < nb_entries:
        reader.info("Looking for CSE Manifest entry")
        entry_name = reader.read_string(12)
        entry_offset = reader.read_dw()
        entry_length = reader.read_dw()
        # reserved field
        reader.read_dw()

        hdr_entry = Component("cse_hdr_entry", "Entry", reader.get_offset())
        hdr_entry.add_a(Astring("entry_name", entry_name))
        hdr_entry.add_a(Ahex("entry_offset", entry_offset))
        hdr_entry.add_a(Ahex("entry_length", entry_length))
        hdr.add_comp(hdr_entry)

        reader.info(
            "CSE Entry name {} length {}".format(entry_name, entry_length)
        )

        if ".man" in entry_name:
            entry = CssManifest(
                entry_name, reader.ext_mft_length + entry_offset
            )
            cur_off = reader.set_offset(reader.ext_mft_length + entry_offset)
            parse_css_manifest(
                entry,
                reader,
                reader.ext_mft_length + entry_offset + entry_length,
            )  # noqa: 501
            reader.set_offset(cur_off)
        elif ".met" in entry_name:
            cur_off = reader.set_offset(reader.ext_mft_length + entry_offset)
            entry = parse_mft_extension(reader, 0)
            entry.name = "{} ({})".format(entry_name, entry.name)
            reader.set_offset(cur_off)
        else:
            # indicate the place, the entry is enumerated. mft parsed later
            entry = Component("adsp_mft_cse_entry", entry_name, entry_offset)
        cse_mft.add_comp(entry)

        nb_index += 1

    return cse_mft


def parse_css_manifest(css_mft, reader, limit):
    """Parses CSS manifest from sof binary"""
    reader.info("Parsing CSS Manifest")
    (ver,) = struct.unpack("I", reader.get_data(0, 4))
    if ver == 4:
        reader.info("CSS Manifest type 4")
        return parse_css_manifest_4(css_mft, reader, limit)

    reader.error("CSS Manifest NOT found or NOT recognized!")
    sys.exit(1)


def parse_css_manifest_4(css_mft, reader, size_limit):
    """Parses CSS manifest type 4 from sof binary"""

    reader.info("Parsing CSS Manifest type 4")
    # CSS Header
    hdr = Component("css_mft_hdr", "Header", reader.get_offset())
    css_mft.add_comp(hdr)

    hdr.add_a(Auint("type", reader.read_dw()))
    header_len_dw = reader.read_dw()
    hdr.add_a(Auint("header_len_dw", header_len_dw))
    hdr.add_a(Auint("header_version", reader.read_dw()))
    hdr.add_a(Auint("reserved0", reader.read_dw(), "red"))
    hdr.add_a(Ahex("mod_vendor", reader.read_dw()))
    hdr.add_a(Adate("date", hex(reader.read_dw())))
    size = reader.read_dw()
    hdr.add_a(Auint("size", size))
    hdr.add_a(Astring("header_id", reader.read_string(4)))
    hdr.add_a(Auint("padding", reader.read_dw()))
    hdr.add_a(
        Aversion(
            "fw_version",
            reader.read_w(),
            reader.read_w(),
            reader.read_w(),
            reader.read_w(),
        )
    )
    hdr.add_a(Auint("svn", reader.read_dw()))
    reader.read_bytes(18 * 4)
    modulus_size = reader.read_dw()
    hdr.add_a(Adec("modulus_size", modulus_size))
    exponent_size = reader.read_dw()
    hdr.add_a(Adec("exponent_size", exponent_size))
    modulus = reader.read_bytes(modulus_size * 4)
    hdr.add_a(Amodulus("modulus", modulus, KNOWN_KEYS.get(modulus, "Other")))
    hdr.add_a(Abytes("exponent", reader.read_bytes(exponent_size * 4)))
    hdr.add_a(Abytes("signature", reader.read_bytes(modulus_size * 4)))

    # Move right after the header
    reader.set_offset(css_mft.file_offset + header_len_dw * 4)

    # Anything packed here is
    #   either an 'Extension' beginning with
    #     dw0 - extension type
    #     dw1 - extension length (in bytes)
    #   that could be parsed if extension type is recognized
    #
    #   or series of 0xffffffff that should be skipped
    reader.info(
        "Parsing CSS Manifest extensions end 0x{:x}".format(size_limit)
    )
    ext_idx = 0
    while reader.get_offset() < size_limit:
        ext_type = reader.read_dw()
        reader.info("Reading extension type 0x{:x}".format(ext_type))
        if ext_type == 0xFFFFFFFF:
            continue
        reader.set_offset(reader.get_offset() - 4)
        css_mft.add_comp(parse_mft_extension(reader, ext_idx))
        ext_idx += 1

    return css_mft


def parse_mft_extension(reader, ext_id):
    """Parses mft extension from sof binary"""
    ext_type = reader.read_dw()
    ext_len = reader.read_dw()
    if ext_type == 15:
        begin_off = reader.get_offset()
        ext = PlatFwAuthExtension(ext_id, reader.get_offset() - 8)
        ext.add_a(Astring("name", reader.read_string(4)))
        ext.add_a(Auint("vcn", reader.read_dw()))
        ext.add_a(Abytes("bitmap", reader.read_bytes(16), "red"))
        ext.add_a(Auint("svn", reader.read_dw()))
        read_len = reader.get_offset() - begin_off
        reader.ff_data(ext_len - read_len)
    elif ext_type == 17:
        ext = AdspMetadataFileExt(ext_id, reader.get_offset() - 8)
        ext.add_a(Auint("adsp_imr_type", reader.read_dw(), "red"))
        # skip reserved part
        reader.read_bytes(16)
        reader.read_dw()
        reader.read_dw()
        #
        ext.add_a(Auint("version", reader.read_dw()))
        ext.add_a(Abytes("sha_hash", reader.read_bytes(32)))
        ext.add_a(Auint("base_offset", reader.read_dw()))
        ext.add_a(Auint("limit_offset", reader.read_dw()))
        ext.add_a(Abytes("attributes", reader.read_bytes(16)))
    else:
        ext = MftExtension(ext_id, "Other Extension", reader.get_offset() - 8)
        reader.ff_data(ext_len - 8)
    ext.add_a(Auint("type", ext_type))
    ext.add_a(Auint("length", ext_len))
    return ext


def parse_adsp_manifest_hdr(reader):
    """Parses ADSP manifest hader from sof binary"""
    # Verify signature
    try:
        sig = reader.read_string(4)
    except UnicodeDecodeError:
        print(
            "\n"
            + reader.offset_to_string()
            + "\terror: Failed to decode signature, wrong position?"
        )
        sys.exit(1)
    if sig != "$AM1":
        reader.error("ADSP Manifest NOT found!", -4)
        sys.exit(1)
    reader.info("ADSP Manifest (" + sig + ")", -4)

    hdr = Component(
        "adsp_mft_hdr", "ADSP Manifest Header", reader.get_offset() - 4
    )
    hdr.add_a(Astring("sig", sig))

    hdr.add_a(Auint("size", reader.read_dw()))
    hdr.add_a(Astring("name", chararr_to_string(reader.read_bytes(8), 8)))
    hdr.add_a(Auint("preload", reader.read_dw()))
    hdr.add_a(Auint("fw_image_flags", reader.read_dw()))
    hdr.add_a(Auint("feature_mask", reader.read_dw()))
    hdr.add_a(
        Aversion(
            "build_version",
            reader.read_w(),
            reader.read_w(),
            reader.read_w(),
            reader.read_w(),
        )
    )

    hdr.add_a(Adec("num_module_entries", reader.read_dw()))
    hdr.add_a(Ahex("hw_buf_base_addr", reader.read_dw()))
    hdr.add_a(Auint("hw_buf_length", reader.read_dw()))
    hdr.add_a(Ahex("load_offset", reader.read_dw()))

    return hdr


def parse_adsp_manifest_mod_entry(index, reader):
    """Parses ADSP manifest module entry from sof binary"""
    # Verify Mod Entry signature
    try:
        sig = reader.read_string(4)
    except UnicodeDecodeError:
        print(
            reader.offset_to_string()
            + "\terror: Failed to decode ModuleEntry signature"
        )
        sys.exit(1)
    if sig != "$AME":
        reader.error("ModuleEntry signature NOT found!")
        sys.exit(1)
    reader.info("Module Entry signature found (" + sig + ")", -4)

    mod = AdspModuleEntry("mod_entry_" + repr(index), reader.get_offset() - 4)
    mod.add_a(Astring("sig", sig))

    mod.add_a(Astring("mod_name", chararr_to_string(reader.read_bytes(8), 8)))
    mod.add_a(Astring("uuid", reader.read_uuid()))
    me_type = reader.read_dw()
    mod.add_a(
        Astring("type", hex(me_type) + " " + mod_type_to_string(me_type))
    )
    mod.add_a(Abytes("hash", reader.read_bytes(32)))
    mod.add_a(Ahex("entry_point", reader.read_dw()))
    mod.add_a(Adec("cfg_offset", reader.read_w()))
    mod.add_a(Adec("cfg_count", reader.read_w()))
    mod.add_a(Auint("affinity_mask", reader.read_dw()))
    mod.add_a(Adec("instance_max_count", reader.read_w()))
    mod.add_a(Auint("instance_stack_size", reader.read_w()))
    for i in range(0, 3):
        seg_flags = reader.read_dw()
        mod.add_a(
            Astring(
                "seg_" + repr(i) + "_flags",
                hex(seg_flags) + " " + seg_flags_to_string(seg_flags),
            )
        )  # noqa: 501
        mod.add_a(Ahex("seg_" + repr(i) + "_v_base_addr", reader.read_dw()))
        mod.add_a(
            Ahex(
                "seg_" + repr(i) + "_size",
                ((seg_flags >> 16) & 0xFFFF) * 0x1000,
            )
        )
        mod.add_a(Ahex("seg_" + repr(i) + "_file_offset", reader.read_dw()))

    return mod


def parse_adsp_manifest(reader, name):
    """Parses ADSP manifest from sof binary"""
    adsp_mft = AdspManifest(name, reader.get_offset())
    adsp_mft.add_comp(parse_adsp_manifest_hdr(reader))
    num_module_entries = (
        adsp_mft.cdir["adsp_mft_hdr"].adir["num_module_entries"].val
    )  # noqa: 501
    for i in range(0, num_module_entries):
        mod_entry = parse_adsp_manifest_mod_entry(i, reader)
        adsp_mft.add_comp(mod_entry)

    return adsp_mft


def parse_fw_bin(path, no_cse, verbose):
    """Parses sof binary"""
    reader = BinReader(path, verbose)

    parsed_bin = FwBin()
    parsed_bin.add_a(Astring("file_name", reader.file_name))
    parsed_bin.add_a(Auint("file_size", reader.file_size))
    parsed_bin.add_comp(parse_extended_manifest(reader))
    if not no_cse:
        parsed_bin.add_comp(parse_cse_manifest(reader))
    reader.set_offset(reader.ext_mft_length + 0x2000)
    parsed_bin.add_comp(parse_adsp_manifest(reader, "cavs0015"))

    reader.info("Parsing finished", show_offset=False)
    return parsed_bin


class BinReader:
    """sof binary reader"""

    def __init__(self, path, verbose):
        self.verbose = verbose
        self.cur_offset = 0
        self.ext_mft_length = 0
        self.info("Reading SOF ri image " + path, show_offset=False)
        self.file_name = path
        # read the content
        self.data = open(path, "rb").read()
        self.file_size = len(self.data)
        self.info(
            "File size " + uint_to_string(self.file_size, True),
            show_offset=False,
        )

    def get_offset(self):
        """Retrieve the offset, the reader is at"""
        return self.cur_offset

    def ff_data(self, delta_offset):
        """Forwards the read pointer by specified number of bytes"""
        self.cur_offset += delta_offset

    def set_offset(self, offset):
        """Set current reader offset"""
        old_offset = self.cur_offset
        self.cur_offset = offset
        return old_offset

    def get_data(self, beg, length):
        """Retrieves the data from beg to beg+length.
        This one is good to peek the data w/o advancing the read pointer
        """
        return self.data[
            self.cur_offset + beg : self.cur_offset + beg + length
        ]

    def read_bytes(self, count):
        """Reads the specified number of bytes from the stream"""
        bts = self.get_data(0, count)
        self.ff_data(count)
        return bts

    def read_dw(self):
        """Reads a dword from the stream"""
        (dword,) = struct.unpack("I", self.get_data(0, 4))
        self.ff_data(4)
        return dword

    def read_w(self):
        """Reads a word from the stream"""
        (word,) = struct.unpack("H", self.get_data(0, 2))
        self.ff_data(2)
        return word

    def read_b(self):
        """Reads a byte from the stream"""
        (byte,) = struct.unpack("B", self.get_data(0, 1))
        self.ff_data(1)
        return byte

    def read_string(self, size_in_file):
        """Reads a string from the stream, potentially padded with zeroes"""
        return self.read_bytes(size_in_file).decode().rstrip("\0")

    def read_uuid(self):
        """Reads a UUID from the stream and returns as string"""
        out = "{:08x}".format(self.read_dw())
        out += "-" + "{:04x}".format(self.read_w())
        out += "-" + "{:04x}".format(self.read_w())
        out += (
            "-"
            + "{:02x}".format(self.read_b())
            + "{:02x}".format(self.read_b())
            + "-"
        )
        for _ in range(0, 6):
            out += "{:02x}".format(self.read_b())
        return out

    def offset_to_string(self, delta=0):
        """Retrieves readable representation of the current offset value"""
        return uint_to_string(self.cur_offset + delta)

    def info(self, loginfo, off_delta=0, verb_info=True, show_offset=True):
        """Prints 'info' log to the output, respects verbose mode"""
        if verb_info and not self.verbose:
            return
        if show_offset:
            print(self.offset_to_string(off_delta) + "\t" + loginfo)
        else:
            print(loginfo)

    def error(self, logerror, off_delta=0):
        """Prints 'error' log to the output"""
        print(self.offset_to_string(off_delta) + "\terror: " + logerror)


# Data Model


class Attribute:
    """Attribute: base class with global formatting options"""

    no_colors = False
    full_bytes = True


class Auint(Attribute):
    """Attribute : unsigned integer"""

    def __init__(self, name, val, color="none"):
        self.name = name
        self.val = val
        self.color = color

    def __str__(self):
        if Attribute.no_colors:
            return uint_to_string(self.val)
        return "{}{}{}".format(
            change_color(self.color),
            uint_to_string(self.val),
            change_color("none"),
        )


class Ahex(Attribute):
    """Attribute : unsigned integer printed as hex"""

    def __init__(self, name, val, color="none"):
        self.name = name
        self.val = val
        self.color = color

    def __str__(self):
        if Attribute.no_colors:
            return hex(self.val)
        return "{}{}{}".format(
            change_color(self.color), hex(self.val), change_color("none")
        )


class Adec(Attribute):
    """Attribute: integer printed as dec"""

    def __init__(self, name, val):
        self.name = name
        self.val = val

    def __str__(self):
        return repr(self.val)


class Abytes(Attribute):
    """Attribute: array of bytes"""

    def __init__(self, name, val, color="none"):
        self.name = name
        self.val = val
        self.color = color

    def __str__(self):
        length = len(self.val)
        if Attribute.no_colors:
            out = ""
        else:
            out = "{}".format(change_color(self.color))
        if Attribute.full_bytes or length <= 16:
            out += " ".join(["{:02x}".format(b) for b in self.val])
        else:
            out += " ".join("{:02x}".format(b) for b in self.val[:8])
            out += " ... "
            out += " ".join(
                "{:02x}".format(b) for b in self.val[length - 8 : length]
            )
        if not Attribute.no_colors:
            out += "{}".format(change_color("none"))
        return out


class Adate(Attribute):
    """Attribute: Date in BCD format"""

    def __init__(self, name, val):
        self.name = name
        self.val = val

    def __str__(self):
        return date_to_string(self.val)


class Astring(Attribute):
    """Attribute: String"""

    def __init__(self, name, val):
        self.name = name
        self.val = val

    def __str__(self):
        return self.val


class Aversion(Attribute):
    """Attribute: version"""

    def __init__(self, name, major, minor, hotfix, build):
        self.name = name
        self.val = "{:d}.{:d}.{:d}.{:d}".format(major, minor, hotfix, build)

    def __str__(self):
        return self.val


class Amodulus(Abytes):
    """Attribute: modulus from RSA public key"""

    def __init__(self, name, val, val_type):
        super().__init__(name, val)
        self.val_type = val_type

    def __str__(self):
        out = super().__str__()
        if not Attribute.full_bytes:
            if Attribute.no_colors:
                out += " ({})".format(self.val_type)
            else:
                out += " {}({}){}".format(
                    change_color("red"), self.val_type, change_color("none")
                )
        return out


class Component:
    """A component of sof binary"""

    def __init__(self, uid, name, file_offset):
        self.uid = uid
        self.name = name
        self.file_offset = file_offset
        self.attribs = []
        self.adir = {}
        self.max_attr_name_len = 0
        self.components = []
        self.cdir = {}

    def add_a(self, attrib):
        """Adds an attribute"""
        self.max_attr_name_len = max(self.max_attr_name_len, len(attrib.name))
        self.attribs.append(attrib)
        self.adir[attrib.name] = attrib

    def add_comp(self, comp):
        """Adds a nested component"""
        self.components.append(comp)
        self.cdir[comp.uid] = comp

    def get_comp(self, comp_uid):
        """Retrieves a nested component by id"""
        for comp in self.components:
            if comp.uid == comp_uid:
                return comp
        return None

    def dump_info(self, pref, comp_filter):
        """Prints out the content (name, all attributes, and nested comps)"""
        print(pref + self.name)
        for attrib in self.attribs:
            print(
                "{:}  {:<{:}} {:}".format(
                    pref, attrib.name, self.max_attr_name_len, attrib
                )
            )
        self.dump_comp_info(pref, comp_filter)

    def dump_attrib_info(self, pref, attr_name):
        """Prints out a single attribute"""
        attrib = self.adir[attr_name]
        print(
            "{:}  {:<{:}} {:}".format(
                pref, attrib.name, self.max_attr_name_len, attrib
            )
        )

    def dump_comp_info(self, pref, comp_filter=""):
        """Prints out all nested components (filtered by name set to 'filter')"""
        for comp in self.components:
            if comp.name in comp_filter:
                continue
            print()
            comp.dump_info(pref + "  ", comp_filter)

    def add_comp_to_mem_map(self, mem_map):
        for comp in self.components:
            comp.add_comp_to_mem_map(mem_map)


class ExtendedManifestAE1(Component):
    """Extended manifest"""

    def __init__(self):
        super(ExtendedManifestAE1, self).__init__(
            "ext_mft", "Extended Manifest", 0
        )

    def dump_info(self, pref, comp_filter):
        hdr = self.cdir["ext_mft_hdr"]
        if hdr.adir["length"].val == 0:
            return
        out = "{}{}".format(pref, self.name)
        out += " ver {}".format(hdr.adir["ver"])
        out += " entries {}".format(hdr.adir["entries"])
        print(out)
        self.dump_comp_info(pref, comp_filter + ["Header"])


class ExtendedManifestXMan(Component):
    """Extended manifest"""

    def __init__(self):
        super(ExtendedManifestXMan, self).__init__(
            "ext_mft", "Extended Manifest", 0
        )

    def dump_info(self, pref, comp_filter):
        hdr = self.cdir["ext_mft_hdr"]
        if hdr.adir["length"].val == 0:
            return
        out = "{}{}".format(pref, self.name)
        out += " ver {}".format(hdr.adir["ver"])
        out += " length {}".format(hdr.adir["length"].val)
        print(out)
        self.dump_comp_info(pref, comp_filter + ["Header"])


class CseManifest(Component):
    """CSE Manifest"""

    def __init__(self, offset):
        super(CseManifest, self).__init__("cse_mft", "CSE Manifest", offset)

    def dump_info(self, pref, comp_filter):
        hdr = self.cdir["cse_mft_hdr"]
        print(
            "{}{} ver {} checksum {} partition name {}".format(
                pref,
                self.name,
                hdr.adir["header_version"],
                hdr.adir["checksum"],
                hdr.adir["partition_name"],
            )
        )
        self.dump_comp_info(pref, comp_filter + ["Header"])


class CssManifest(Component):
    """CSS Manifest"""

    def __init__(self, name, offset):
        super(CssManifest, self).__init__("css_mft", name, offset)

    def dump_info(self, pref, comp_filter):
        hdr = self.cdir["css_mft_hdr"]
        out = "{}{} (CSS Manifest)".format(pref, self.name)
        out += " type {}".format(hdr.adir["type"])
        out += " ver {}".format(hdr.adir["header_version"])
        out += " date {}".format(hdr.adir["date"])
        print(out)
        print("{}  Rsvd0 {}".format(pref, hdr.adir["reserved0"]))
        print(
            "{}  Modulus size (dwords) {}".format(
                pref, hdr.adir["modulus_size"]
            )
        )
        print("{}    {}".format(pref, hdr.adir["modulus"]))
        print(
            "{}  Exponent size (dwords) {}".format(
                pref, hdr.adir["exponent_size"]
            )
        )
        print("{}    {}".format(pref, hdr.adir["exponent"]))
        print("{}  Signature".format(pref))
        print("{}    {}".format(pref, hdr.adir["signature"]))
        # super().dump_info(pref)
        self.dump_comp_info(pref, comp_filter + ["Header"])


class MftExtension(Component):
    """Manifest Extension"""

    def __init__(self, ext_id, name, offset):
        super(MftExtension, self).__init__(
            "mft_ext" + repr(ext_id), name, offset
        )

    def dump_info(self, pref, comp_filter):
        print(
            "{}{} type {} length {}".format(
                pref, self.name, self.adir["type"], self.adir["length"]
            )
        )


class PlatFwAuthExtension(MftExtension):
    """Platform FW Auth Extension"""

    def __init__(self, ext_id, offset):
        super(PlatFwAuthExtension, self).__init__(
            ext_id, "Plat Fw Auth Extension", offset
        )

    def dump_info(self, pref, comp_filter):
        out = "{}{}".format(pref, self.name)
        out += " name {}".format(self.adir["name"])
        out += " vcn {}".format(self.adir["vcn"])
        out += " bitmap {}".format(self.adir["bitmap"])
        out += " svn {}".format(self.adir["svn"])
        print(out)


class AdspMetadataFileExt(MftExtension):
    """ADSP Metadata File Extension"""

    def __init__(self, ext_id, offset):
        super(AdspMetadataFileExt, self).__init__(
            ext_id, "ADSP Metadata File Extension", offset
        )

    def dump_info(self, pref, comp_filter):
        out = "{}{}".format(pref, self.name)
        out += " ver {}".format(self.adir["version"])
        out += " base offset {}".format(self.adir["base_offset"])
        out += " limit offset {}".format(self.adir["limit_offset"])
        print(out)
        print("{}  IMR type {}".format(pref, self.adir["adsp_imr_type"]))
        print("{}  Attributes".format(pref))
        print("{}    {}".format(pref, self.adir["attributes"]))


class AdspManifest(Component):
    """ADSP Manifest"""

    def __init__(self, name, offset):
        super(AdspManifest, self).__init__("adsp_mft", name, offset)

    def dump_info(self, pref, comp_filter):
        hdr = self.cdir["adsp_mft_hdr"]
        out = "{}{} (ADSP Manifest)".format(pref, self.name)
        out += " name {}".format(hdr.adir["name"])
        out += " build ver {}".format(hdr.adir["build_version"])
        out += " feature mask {}".format(hdr.adir["feature_mask"])
        out += " image flags {}".format(hdr.adir["fw_image_flags"])
        print(out)
        print(
            "{}  HW buffers base address {} length {}".format(
                pref, hdr.adir["hw_buf_base_addr"], hdr.adir["hw_buf_length"]
            )
        )
        print("{}  Load offset {}".format(pref, hdr.adir["load_offset"]))
        self.dump_comp_info(pref, comp_filter + ["ADSP Manifest Header"])


class AdspModuleEntry(Component):
    """ADSP Module Entry"""

    def __init__(self, uid, offset):
        super(AdspModuleEntry, self).__init__(uid, "Module Entry", offset)

    def dump_info(self, pref, comp_filter):
        print(
            "{}{:9} {}".format(
                pref, str(self.adir["mod_name"]), self.adir["uuid"]
            )
        )
        print(
            "{}  entry point {} type {}".format(
                pref, self.adir["entry_point"], self.adir["type"]  # noqa: 501
            )
        )
        out = "{}  cfg offset {} count {} affinity {}".format(
            pref,
            self.adir["cfg_offset"],
            self.adir["cfg_count"],  # noqa: 501
            self.adir["affinity_mask"],
        )  # noqa: 501
        out += " instance max count {} stack size {}".format(
            self.adir["instance_max_count"], self.adir["instance_stack_size"]
        )
        print(out)
        print(
            "{}  .text   {} file offset {} flags {}".format(
                pref,
                self.adir["seg_0_v_base_addr"],
                self.adir["seg_0_file_offset"],  # noqa: 501
                self.adir["seg_0_flags"],
            )
        )  # noqa: 501
        print(
            "{}  .rodata {} file offset {} flags {}".format(
                pref,
                self.adir["seg_1_v_base_addr"],
                self.adir["seg_1_file_offset"],  # noqa: 501
                self.adir["seg_1_flags"],
            )
        )  # noqa: 501
        print(
            "{}  .bss    {} file offset {} flags {}".format(
                pref,
                self.adir["seg_2_v_base_addr"],
                self.adir["seg_2_file_offset"],  # noqa: 501
                self.adir["seg_2_flags"],
            )
        )  # noqa: 501

    def add_comp_to_mem_map(self, mem_map):
        mem_map.insert_segment(
            DspMemorySegment(
                self.adir["mod_name"].val + ".text",
                self.adir["seg_0_v_base_addr"].val,
                self.adir["seg_0_size"].val,
            )
        )
        mem_map.insert_segment(
            DspMemorySegment(
                self.adir["mod_name"].val + ".rodata",
                self.adir["seg_1_v_base_addr"].val,
                self.adir["seg_1_size"].val,
            )
        )
        mem_map.insert_segment(
            DspMemorySegment(
                self.adir["mod_name"].val + ".bss",
                self.adir["seg_2_v_base_addr"].val,
                self.adir["seg_2_size"].val,
            )
        )


class FwBin(Component):
    """Parsed sof binary"""

    def __init__(self):
        super(FwBin, self).__init__("bin", "SOF Binary", 0)

    def dump_info(self, pref, comp_filter):
        """Print out the content"""
        print(
            "SOF Binary {} size {}".format(
                self.adir["file_name"], self.adir["file_size"]
            )
        )
        self.dump_comp_info(pref, comp_filter)

    def populate_mem_map(self, mem_map):
        """Adds modules' segments to the memory map"""
        self.add_comp_to_mem_map(mem_map)


# DSP Memory Layout


def get_mem_map(ri_path):
    """Retrieves memory map for platform determined by the file name"""
    for plat_name in DSP_MEM_SPACE_EXT:
        if plat_name in ri_path:
            return DSP_MEM_SPACE_EXT[plat_name]
    return DspMemory("Memory layout undefined", [])


def add_lmap_mem_info(ri_path, mem_map):
    """Optional lmap processing"""
    lmap_path = ri_path[0 : ri_path.rfind(".")] + ".lmap"
    try:
        with open(lmap_path) as lmap:
            it_lines = iter(lmap.readlines())
            for line in it_lines:
                if "Sections:" in line:
                    next(it_lines)
                    break
            for line in it_lines:
                tok = line.split()
                mem_map.insert_segment(
                    DspMemorySegment(tok[1], int(tok[3], 16), int(tok[2], 16))
                )  # noqa: 501
                next(it_lines)

    except FileNotFoundError:
        return


class DspMemorySegment(object):
    """Single continuous memory space"""

    def __init__(self, name, base_address, size):
        self.name = name
        self.base_address = base_address
        self.size = size
        self.used_size = 0
        self.inner_segments = []

    def is_inner(self, segment):
        return (
            self.base_address <= segment.base_address
            and segment.base_address + segment.size
            <= self.base_address + self.size
        )  # noqa: 501

    def insert_segment(self, segment):
        for seg in self.inner_segments:
            if seg.is_inner(segment):
                seg.insert_segment(segment)
                return
        self.inner_segments.append(segment)
        self.used_size += segment.size

    def dump_info(self, pref):
        free_size = self.size - self.used_size
        out = "{}{:<35} 0x{:x}".format(pref, self.name, self.base_address)
        if self.used_size > 0:
            out += " ({} + {}  {:.2f}% used)".format(
                self.used_size, free_size, self.used_size * 100 / self.size
            )  # noqa: 501
        else:
            out += " ({})".format(free_size)
        print(out)
        for seg in self.inner_segments:
            seg.dump_info(pref + "  ")


class DspMemory(object):
    """Dsp Memory, all top-level segments"""

    def __init__(self, platform_name, segments):
        self.platform_name = platform_name
        self.segments = segments

    def insert_segment(self, segment):
        """Inserts segment"""
        for seg in self.segments:
            if seg.is_inner(segment):
                seg.insert_segment(segment)
                return

    def dump_info(self):
        print(self.platform_name)
        for seg in self.segments:
            seg.dump_info("  ")


# Layouts of DSP memory for known platforms


APL_MEMORY_SPACE = DspMemory(
    "Intel Apollolake",
    [
        DspMemorySegment("imr", 0xA0000000, 4 * 1024 * 1024),
        DspMemorySegment("l2 hpsram", 0xBE000000, 8 * 64 * 1024),
        DspMemorySegment("l2 lpsram", 0xBE800000, 2 * 64 * 1024),
    ],
)

CNL_MEMORY_SPACE = DspMemory(
    "Intel Cannonlake",
    [
        DspMemorySegment("imr", 0xB0000000, 8 * 0x1024 * 0x1024),
        DspMemorySegment("l2 hpsram", 0xBE000000, 48 * 64 * 1024),
        DspMemorySegment("l2 lpsram", 0xBE800000, 1 * 64 * 1024),
    ],
)

ICL_MEMORY_SPACE = DspMemory(
    "Intel Icelake",
    [
        DspMemorySegment("imr", 0xB0000000, 8 * 1024 * 1024),
        DspMemorySegment("l2 hpsram", 0xBE000000, 47 * 64 * 1024),
        DspMemorySegment("l2 lpsram", 0xBE800000, 1 * 64 * 1024),
    ],
)

TGL_LP_MEMORY_SPACE = DspMemory(
    "Intel Tigerlake-LP",
    [
        DspMemorySegment("imr", 0xB0000000, 16 * 1024 * 1024),
        DspMemorySegment("l2 hpsram", 0xBE000000, 46 * 64 * 1024),
        DspMemorySegment("l2 lpsram", 0xBE800000, 1 * 64 * 1024),
    ],
)

JSL_MEMORY_SPACE = DspMemory(
    "Intel Jasperlake",
    [
        DspMemorySegment("imr", 0xB0000000, 8 * 1024 * 1024),
        DspMemorySegment("l2 hpsram", 0xBE000000, 16 * 64 * 1024),
        DspMemorySegment("l2 lpsram", 0xBE800000, 1 * 64 * 1024),
    ],
)

TGL_H_MEMORY_SPACE = DspMemory(
    "Intel Tigerlake-H",
    [
        DspMemorySegment("imr", 0xB0000000, 16 * 1024 * 1024),
        DspMemorySegment("l2 hpsram", 0xBE000000, 30 * 64 * 1024),
        DspMemorySegment("l2 lpsram", 0xBE800000, 1 * 64 * 1024),
    ],
)

DSP_MEM_SPACE_EXT = {
    "apl": APL_MEMORY_SPACE,
    "cnl": CNL_MEMORY_SPACE,
    "icl": ICL_MEMORY_SPACE,
    "tgl": TGL_LP_MEMORY_SPACE,
    "jsl": JSL_MEMORY_SPACE,
    "tgl-h": TGL_H_MEMORY_SPACE,
    "ehl": TGL_LP_MEMORY_SPACE,
}


def main(args):
    """main function"""
    if sys.stdout.isatty():
        Attribute.no_colors = args.no_colors
    else:
        Attribute.no_colors = True

    Attribute.full_bytes = args.full_bytes

    fw_bin = parse_fw_bin(args.sof_ri_path, args.no_cse, args.verbose)

    if args.valid:
        css_mft_hdr = (
            fw_bin.get_comp("cse_mft")
            .get_comp("css_mft")
            .get_comp("css_mft_hdr")
        )
        modulus = css_mft_hdr.adir["modulus"]
        if "Other" in modulus.val_type:
            print("%s is not valid" % args.sof_ri_path)
            sys.exit(2)
        sys.exit(0)

    comp_filter = []
    if args.headers or args.no_modules:
        comp_filter.append("Module Entry")
    if args.no_headers:
        comp_filter.append("CSE Manifest")
    fw_bin.dump_info("", comp_filter)
    if not args.no_memory:
        mem = get_mem_map(args.sof_ri_path)
        fw_bin.populate_mem_map(mem)
        add_lmap_mem_info(args.sof_ri_path, mem)
        print()
        mem.dump_info()


if __name__ == "__main__":
    ARGS = parse_params()
    main(ARGS)
