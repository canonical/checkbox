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

CPUIDS = {
        "Amber Lake":       ['0x806e9'],
        "AMD EPYC":         ['0x800f12'],
        "AMD Lisbon":       ['0x100f81'],
        "AMD Magny-Cours":  ['0x100f91'],
        "AMD Milan":        ['0xa00f11'],
        "AMD ROME":         ['0x830f10'],
        "Broadwell":        ['0x4067', '0x306d4', '0x5066', '0x406f'],
        "Canon Lake":       ['0x6066'],
        "Cascade Lake":     ['0x50655', '0x50656', '0x50657'],
        "Coffee Lake":      [
            '0x806ea', '0x906ea', '0x906eb', '0x906ec', '0x906ed'],
        "Comet Lake":       ['0x806ec', '0xa065'],
        "Cooper Lake":      ['0x5065a', '0x5065b'],
        "Haswell":          ['0x306c', '0x4065', '0x4066', '0x306f'],
        "Ice Lake":         ['0x606e6', '0x606a6', '0x706e6'],
        "Ivy Bridge":       ['0x306a', '0x306e'],
        "Kaby Lake":        ['0x806e9', '0x906e9'],
        "Knights Landing":  ['0x5067'],
        "Knights Mill":     ['0x8065'],
        "Nehalem":          ['0x106a', '0x106e5', '0x206e'],
        "Pineview":         ['0x106ca'],
        "Penryn":           ['0x1067a'],
        "Rocket Lake":      ['0xa0671'],
        "Sandy Bridge":     ['0x206a', '0x206d6', '0x206d7'],
        "Skylake":          ['0x406e3', '0x506e3', '0x50654', '0x50652'],
        "Tiger Lake":       ['0x806c1'],
        "Westmere":         ['0x2065', '0x206c', '0x206f'],
        "Whisky Lake":      ['0x806eb', '0x806ec'],
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
    cpuid = CPUID()
    cpu = cpuid(1)

    # Lets play Guess The CPU!
    # First lets get the name from /proc/cpuinfo
    cpu_data = check_output('lscpu', universal_newlines=True).split('\n')
    for line in cpu_data:
        if line.startswith('Model name:'):
            print("CPU Model: %s" % line.split(':')[1].lstrip())

    my_id = (hex(cpu[0]))
    complete = False
    for key in CPUIDS.keys():
        for value in CPUIDS[key]:
            if value in my_id:
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
