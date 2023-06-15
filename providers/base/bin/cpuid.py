#!/usr/bin/env python3

# The MIT License (MIT)
#
# Copyright (c) 2014 Anders Høst
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Modifications: 2019 Jeffrey Lane (jeffrey.lane@canonical.com)

import argparse
from enum import Enum
import ctypes
import platform
import sys
from ctypes import (c_uint32, c_int, c_size_t, c_void_p,
                    POINTER, CFUNCTYPE)
from subprocess import check_output

# Posix x86_64:
# Three first call registers : RDI, RSI, RDX
# Volatile registers         : RAX, RCX, RDX, RSI, RDI, R8-11

# Windows x86_64:
# Three first call registers : RCX, RDX, R8
# Volatile registers         : RAX, RCX, RDX, R8-11

# cdecl 32 bit:
# Three first call registers : Stack (%esp)
# Volatile registers         : EAX, ECX, EDX

_POSIX_64_OPC = [
        0x53,                    # push   %rbx
        0x89, 0xf0,              # mov    %esi,%eax
        0x89, 0xd1,              # mov    %edx,%ecx
        0x0f, 0xa2,              # cpuid
        0x89, 0x07,              # mov    %eax,(%rdi)
        0x89, 0x5f, 0x04,        # mov    %ebx,0x4(%rdi)
        0x89, 0x4f, 0x08,        # mov    %ecx,0x8(%rdi)
        0x89, 0x57, 0x0c,        # mov    %edx,0xc(%rdi)
        0x5b,                    # pop    %rbx
        0xc3                     # retq
]

_CDECL_32_OPC = [
        0x53,                    # push   %ebx
        0x57,                    # push   %edi
        0x8b, 0x7c, 0x24, 0x0c,  # mov    0xc(%esp),%edi
        0x8b, 0x44, 0x24, 0x10,  # mov    0x10(%esp),%eax
        0x8b, 0x4c, 0x24, 0x14,  # mov    0x14(%esp),%ecx
        0x0f, 0xa2,              # cpuid
        0x89, 0x07,              # mov    %eax,(%edi)
        0x89, 0x5f, 0x04,        # mov    %ebx,0x4(%edi)
        0x89, 0x4f, 0x08,        # mov    %ecx,0x8(%edi)
        0x89, 0x57, 0x0c,        # mov    %edx,0xc(%edi)
        0x5f,                    # pop    %edi
        0x5b,                    # pop    %ebx
        0xc3                     # ret
]

is_64bit = ctypes.sizeof(ctypes.c_voidp) == 8

# EAX bitmap explaination
# [31:28] Reserved
# [27:20] Extended Family
# [19:16] Extended Model
# [15:14] Reserved
# [13:12] Processor Type
# [11:8]  Family
# [7:4]   Model
# [3:0]   Stepping

# Intel CPUID Hex Mapping
# 0x[1][2][3][4][5]
# [1] Extended Model
# [2] Extended Family
# [3] Family
# [4] Model
# [5] Stepping

# AMD CPUID Hex Mapping
# 0x[1][2][3][4][5][6]
# [1] Extended Family
# [2] Extended Model
# [3] Reserved
# [4] Base Family
# [5] Base Model
# [6] Stepping


class ChipType(Enum):
    SERVER = 1
    CLIENT = 2


# Some CPUIDs are full IDs, and others omit the last digit
CPUDICT = {
        "AMD EPYC":         {
                                "cpuids": ['0x800f12'],
                                "generation":   -1,  # noqa
                                "chiptype":     ChipType.SERVER
                            },
        "AMD Genoa":        {
                                "cpuids": ['0xa10f11'],
                                "generation":   -1, # noqa
                                "chiptype":     ChipType.SERVER
                            },
        "AMD Lisbon":       {
                                "cpuids": ['0x100f81'],
                                "generation":   -1, # noqa
                                "chiptype":     ChipType.SERVER
                            },
        "AMD Magny-Cours":  {
                                "cpuids": ['0x100f91'],
                                "generation":   -1, # noqa
                                "chiptype":     ChipType.SERVER
                            },
        "AMD Milan":        {
                                "cpuids": ['0xa00f11'],
                                "generation":   -1, # noqa
                                "chiptype":     ChipType.SERVER
                            },
        "AMD Milan-X":      {
                                "cpuids": ['0xa00f12'],
                                "generation":   -1, # noqa
                                "chiptype":     ChipType.SERVER
                            },
        "AMD ROME":         {
                                "cpuids": ['0x830f10'],
                                "generation":   -1, # noqa
                                "chiptype":     ChipType.SERVER
                            },
        "AMD Ryzen":        {
                                "cpuids": ['0x810f81'],
                                "generation":   -1, # noqa
                                "chiptype":     ChipType.CLIENT
                            },
        "AMD Bergamo":      {
                                "cpuids": ['0xaa0f01'],
                                "generation":   -1, # noqa
                                "chiptype":     ChipType.SERVER
                            },
        "Broadwell":        {
                                "cpuids": ['0x4067', '0x306d4'],
                                "generation":   5,
                                "chiptype":     ChipType.CLIENT
                            },
        "Broadwell Xeon":   {
                                "cpuids": ['0x5066', '0x406f'],
                                "generation":   -1, # noqa
                                "chiptype":     ChipType.SERVER
                            },
        "Cannon Lake":      {
                                "cpuids": ['0x6066'],
                                "generation":   8,
                                "chiptype":     ChipType.CLIENT
                            },
        "Cascade Lake":     {
                                "cpuids": ['0x50655', '0x50656', '0x50657'],
                                "generation":   2,
                                "chiptype":     ChipType.SERVER
                            },
        "Coffee Lake":      {
                                "cpuids": ['0x806ea', '0x906ea', '0x906eb',
                                           '0x906ec', '0x906ed'],
                                "generation":   8,
                                "chiptype":     ChipType.CLIENT
                            },
        "Comet Lake":       {
                                "cpuids": ['0x806ec', '0xa065'],
                                "generation":   10,
                                "chiptype":     ChipType.CLIENT
                            },
        "Cooper Lake":      {
                                "cpuids": ['0x5065a', '0x5065b'],
                                "generation":   3,
                                "chiptype":     ChipType.SERVER
                            },
        "Haswell":          {
                                "cpuids": ['0x306c', '0x4065', '0x4066'],
                                "generation":   4,
                                "chiptype":     ChipType.CLIENT
                            },
        "Haswell Xeon":     {
                                "cpuids": ['0x306f'],
                                "generation":   -1, # noqa
                                "chiptype":     ChipType.SERVER
                            },
        "Ice Lake":          {
                                "cpuids": ['0x606e6', '0x706e6'],
                                "generation":   10,
                                "chiptype":     ChipType.CLIENT
                            },
        "Ice Lake Xeon":    {
                                "cpuids": ['0x606a6', '0x606c1'],
                                "generation":   3,
                                "chiptype":     ChipType.SERVER
                            },
        "Ivy Bridge":       {
                                "cpuids": ['0x306a'],
                                "generation":   3,
                                "chiptype":     ChipType.CLIENT
                            },
        "Ivy Bridge Xeon":       {
                                "cpuids": ['0x306e'],
                                "generation":   -1, # noqa
                                "chiptype":     ChipType.SERVER
                            },
        "Kaby Lake":        {
                                "cpuids": ['0x806e9', '0x906e9', '0x806e9'],
                                "generation":   7,
                                "chiptype":     ChipType.CLIENT
                            },
        "Knights Landing":  {
                                "cpuids": ['0x5067'],
                                "generation":   -1, # noqa
                                "chiptype":     ChipType.SERVER
                            },
        "Knights Mill":     {
                                "cpuids": ['0x8065'],
                                "generation":   -1, # noqa
                                "chiptype":     ChipType.SERVER
                            },
        "Nehalem":          {
                                "cpuids": ['0x106e5'],
                                "generation":   1,
                                "chiptype":     ChipType.CLIENT
                            },
        "Nehalem Xeon":     {
                                "cpuids": ['0x106a', '0x206e'],
                                "generation":   -1, # noqa
                                "chiptype":     ChipType.SERVER
                            },
        "Pineview":          {
                                "cpuids": ['0x106ca'],
                                "generation":   1,
                                "chiptype":     ChipType.CLIENT
                            },
        "Penryn":           {
                                "cpuids": ['0x1067a'],
                                "generation":   -1, # noqa
                                "chiptype":     ChipType.CLIENT
                            },
        "Rocket Lake":      {
                                "cpuids": ['0xa0671'],
                                "generation":   11,
                                "chiptype":     ChipType.CLIENT
                            },
        "Sandy Bridge":     {
                                "cpuids": ['0x206a'],
                                "generation":   2,
                                "chiptype":     ChipType.CLIENT
                            },
        "Sandy Bridge Xeon":     {
                                "cpuids": ['0x206d6', '0x206d7'],
                                "generation":   -1, # noqa
                                "chiptype":     ChipType.SERVER
                            },
        "Sapphire Rapids":  {
                                "cpuids": ['0x806f3', '0x806f6', '0x806f7',
                                           '0x806f8'],
                                "generation":   4,
                                "chiptype":     ChipType.SERVER
                            },
        "Skylake":          {
                                "cpuids": ['0x406e3', '0x506e3'],
                                "generation":   6,
                                "chiptype":     ChipType.CLIENT
                            },
        "Skylake Xeon":     {
                                "cpuids": ['0x50654', '0x50652'],
                                "generation":   1,
                                "chiptype":     ChipType.SERVER
                            },
        "Tiger Lake":       {
                                "cpuids": ['0x806c1'],
                                "generation":   11,
                                "chiptype":     ChipType.CLIENT
                            },
        "Alder Lake":       {
                                "cpuids": ['0x906a4', '0x906A3', '0x90675',
                                           '0x90672', '0x906a2'],
                                "generation":   12,
                                "chiptype":     ChipType.CLIENT
                            },
        "Raptor Lake":      {
                                "cpuids": ['0xB0671', '0xB06F2', '0xB06F5',
                                           '0xB06A2'],
                                "generation":   13,
                                "chiptype":     ChipType.CLIENT
                            },
        "Westmere":         {
                                "cpuids": ['0x2065'],
                                "generation":   1,
                                "chiptype":     ChipType.CLIENT
                            },
        "Westmere Xeon":    {
                                "cpuids": ['0x206c', '0x206f'],
                                "generation":   -1, # noqa
                                "chiptype":     ChipType.SERVER
                            },
        "Whisky Lake":      {
                                "cpuids": ['0x806eb', '0x806ec'],
                                "generation":   10,
                                "chiptype":     ChipType.CLIENT
                            },
        }


class CPUID_struct(ctypes.Structure):
    _fields_ = [(r, c_uint32) for r in ("eax", "ebx", "ecx", "edx")]


class CPUID(object):
    def __init__(self):
        if platform.machine() not in ("AMD64", "x86_64", "x86", "i686"):
            print("ERROR: Only available for x86")
            sys.exit(1)

        opc = _POSIX_64_OPC if is_64bit else _CDECL_32_OPC

        size = len(opc)
        code = (ctypes.c_ubyte * size)(*opc)

        self.libc = ctypes.cdll.LoadLibrary(None)
        self.libc.valloc.restype = ctypes.c_void_p
        self.libc.valloc.argtypes = [ctypes.c_size_t]
        self.addr = self.libc.valloc(size)
        if not self.addr:
            print("ERROR: Could not allocate memory")
            sys.exit(1)

        self.libc.mprotect.restype = c_int
        self.libc.mprotect.argtypes = [c_void_p, c_size_t, c_int]
        ret = self.libc.mprotect(self.addr, size, 1 | 2 | 4)
        if ret != 0:
            print("ERROR: Failed to set RWX")
            sys.exit(1)

        ctypes.memmove(self.addr, code, size)

        func_type = CFUNCTYPE(None, POINTER(CPUID_struct), c_uint32, c_uint32)
        self.func_ptr = func_type(self.addr)

    def __call__(self, eax, ecx=0):
        struct = CPUID_struct()
        self.func_ptr(struct, eax, ecx)
        return struct.eax, struct.ebx, struct.ecx, struct.edx

    def __del__(self):
        # Seems to throw exception when the program ends and
        # libc is cleaned up before the object?
        self.libc.free.restype = None
        self.libc.free.argtypes = [c_void_p]
        self.libc.free(self.addr)


def main():
    parser = argparse.ArgumentParser(
                    prog='cpuid',
                    description='Identifies the Intel generation based on cpu \
                                ids')
    parser.add_argument('--intel_gen_number', action='store_true')
    args = parser.parse_args()

    cpuid = CPUID()
    cpu = cpuid(1)

    # Lets play Guess The CPU!
    # First lets get the name from /proc/cpuinfo
    cpu_data = check_output('lscpu', universal_newlines=True).split('\n')
    for line in cpu_data:
        if line.startswith('Model name:') and not args.intel_gen_number:
            print("CPU Model: %s" % line.split(':')[1].lstrip())

    my_id = (hex(cpu[0]))
    complete = False
    for key in CPUDICT.keys():
        platform = CPUDICT[key]
        platform_ids = platform['cpuids']
        for platform_id in platform_ids:
            if platform_id.lower() in my_id:
                if args.intel_gen_number:
                    if platform['chiptype'] == ChipType.CLIENT and \
                       platform['generation'] > 0:
                        print(platform['generation'])
                    else:
                        print("%s is not supported for conversion to Intel \
                              generation number")
                else:
                    print("CPUID: %s which appears to be a %s processor" %
                          (my_id, key))

                complete = True

    if not complete:
        print("Unable to determine CPU Family for this CPUID: %s" % my_id)
        return 1
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
