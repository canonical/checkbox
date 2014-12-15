# encoding: UTF-8
# Copyright (c) 2014 Canonical Ltd.
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
glibc -- things from glibc that have no python interface
========================================================

This package contains ``ctypes`` based wrappers around several missing
functions from glibc. Only missing objects are provided though. Please get the
rest from python's stdlib (aka ``signal``, ``posix`` and ``os``).

.. note::
    If you found that a glibc function that you'd like to use, is missing,
    please open a bug or provide a patch (it's trivial, just look at existing
    functions as an example). All glibc functions are in scope.
"""
from __future__ import absolute_import
from __future__ import division

from ctypes import POINTER
from ctypes import c_int
from ctypes import c_int32
from ctypes import c_long
from ctypes import c_uint
from ctypes import c_uint32
from ctypes import c_uint64
from ctypes import c_uint8
from ctypes import c_ulong
from ctypes import c_voidp
from ctypes import c_size_t
from ctypes import c_ssize_t
from ctypes import get_errno
from errno import EACCES
from errno import EAGAIN
from errno import EBADF
from errno import EBUSY
from errno import EFAULT
from errno import EINTR
from errno import EINVAL
from errno import EIO
from errno import EISDIR
from errno import EMFILE
from errno import ENFILE
from errno import ENODEV
from errno import ENOMEM
from errno import EPERM
from errno import EWOULDBLOCK
import collections
import ctypes
import ctypes.util
import errno
import inspect
import os
import sys
import types


__all__ = [
    # NOTE: __all__ in this module is magic!
    # This value is extended with types, constants and function from glibc
]
__author__ = 'Zygmunt Krynicki <zygmunt.krynicki@canonical.com>'
__version__ = '0.6.1'


# Load the standard C library on this system
_glibc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
_pthread = ctypes.CDLL(ctypes.util.find_library('pthread'))


class LazyModule(types.ModuleType):
    """
    A module subclass that imports things lazily on demand.

    There are some special provisions to make dir() and __all__ work better so
    that pydoc is more informative.

    :ivar _lazy:
        A mapping of 'name' to 'callable'. The callable is called only once and
        defines the lazily loaded version of 'name'.
    :ivar _all:
        A set of all the "public" objects. This is exposed as the module's
        __all__ property. It automatically collects all the objects reported
        via :meth:`lazily()` and :meth:`immediate()`.
    :ivar _old:
        Reference to the old (original) module. This is kept around for python
        2.x compatibility. It also seems to help with implementing __dir__()
    """

    def __init__(self, name, doc, old):
        super(LazyModule, self).__init__(name, doc)
        self._lazy = {}
        self._all = set()
        self._old = old

    def __dir__(self):
        """
        Lazy-aware version of __dir__()
        """
        if sys.version_info[0] == 3:
            data = super(LazyModule, self).__dir__()
        else:
            data = self.__dict__.keys()
        data = set(data) | self._all
        return sorted(data)

    def __getattr__(self, name):
        """
        Lazy-aware version of __getattr__()
        """
        try:
            callable, args = self._lazy[name]
        except KeyError:
            raise AttributeError(name)
        value = callable(*args)
        del self._lazy[name]
        setattr(self, name, value)
        return value

    @classmethod
    def shadow_normal_module(cls, mod_name=None):
        """
        Shadow a module with an instance of LazyModule

        :param mod_name:
            Name of the module to shadow. By default this is the module that is
            making the call into this method. This is not hard-coded as that
            module might be called '__main__' if it is executed via 'python -m'
        :returns:
            A fresh instance of :class:`LazyModule`.
        """
        if mod_name is None:
            frame = inspect.currentframe()
            try:
                mod_name = frame.f_back.f_locals['__name__']
            finally:
                del frame
        orig_mod = sys.modules[mod_name]
        lazy_mod = cls(orig_mod.__name__, orig_mod.__doc__, orig_mod)
        for attr in dir(orig_mod):
            setattr(lazy_mod, attr, getattr(orig_mod, attr))
        sys.modules[mod_name] = lazy_mod
        return lazy_mod

    def lazily(self, name, callable, args):
        """
        Load something lazily
        """
        self._lazy[name] = callable, args
        self._all.add(name)

    def immediate(self, name, value):
        """
        Load something immediately
        """
        setattr(self, name, value)
        self._all.add(name)

    @property
    def __all__(self):
        """
        A lazy-aware version of __all__

        In addition to exposing all of the original module's __all__ it also
        contains all the (perhaps not yet loaded) objects defined via
        :meth:`lazily()`
        """
        return sorted(self._all)

    @__all__.setter
    def __all__(self, value):
        """
        Setter for __all__ that just updates the internal set :ivar:`_all`

        This is used by :meth:`shadow_normal_module()` which copies (assigns)
        all of the original module's attributes, which also assigns __all__.
        """
        self._all.update(value)


# Replace 'glibc' module in sys.modules with LazyModule
_mod = LazyModule.shadow_normal_module()


_glibc_aliasinfo = collections.namedtuple(
    '_glibc_aliasinfo', 'py_name c_name ctypes_type c_macros')


_glibc_aliases = [
    ('time_t', 'time_t', c_long, ('#include <time.h>',)),
    ('suseconds_t', 'suseconds_t', c_long, ('#include <sys/types.h>',)),
    ('eventfd_t', 'eventfd_t', c_uint64, ('#include <sys/eventfd.h>',)),
    ('clockid_t', 'clockid_t', c_int, ('#include <time.h>',)),
]

_glibc_aliases = [_glibc_aliasinfo(*i) for i in _glibc_aliases]


for info in _glibc_aliases:
    _mod.immediate(info.py_name, info.ctypes_type)
del info


_glibc_typeinfo = collections.namedtuple(
    '_glibc_typeinfo',
    'doc py_kind py_name c_name c_packed py_fields c_macros')


# Lazily define all supported glibc types
_glibc_types = [
    ("""
     struct sigset_t;
     """,
     'struct', 'sigset_t', 'sigset_t', False, (
         # There's no spec on that, pulled from glibc
         ('__val', c_ulong * (1024 // (8 * ctypes.sizeof(c_ulong)))),
     ), [
         '#include <signal.h>'
     ]),
    ("""
     struct signalfd_siginfo {
         uint32_t ssi_signo;   /* Signal number */
         int32_t  ssi_errno;   /* Error number (unused) */
         int32_t  ssi_code;    /* Signal code */
         uint32_t ssi_pid;     /* PID of sender */
         uint32_t ssi_uid;     /* Real UID of sender */
         int32_t  ssi_fd;      /* File descriptor (SIGIO) */
         uint32_t ssi_tid;     /* Kernel timer ID (POSIX timers)
         uint32_t ssi_band;    /* Band event (SIGIO) */
         uint32_t ssi_overrun; /* POSIX timer overrun count */
         uint32_t ssi_trapno;  /* Trap number that caused signal */
         int32_t  ssi_status;  /* Exit status or signal (SIGCHLD) */
         int32_t  ssi_int;     /* Integer sent by sigqueue(3) */
         uint64_t ssi_ptr;     /* Pointer sent by sigqueue(3) */
         uint64_t ssi_utime;   /* User CPU time consumed (SIGCHLD) */
         uint64_t ssi_stime;   /* System CPU time consumed (SIGCHLD) */
         uint64_t ssi_addr;    /* Address that generated signal
                                  (for hardware-generated signals) */
         uint8_t  __pad[48];   /* Pad size to 128 bytes (allow for
                                  additional fields in the future) */
     };""",
     'struct', 'signalfd_siginfo', 'struct signalfd_siginfo', False, (
         ('ssi_signo', c_uint32),
         ('ssi_errno', c_int32),
         ('ssi_code', c_int32),
         ('ssi_pid', c_uint32),
         ('ssi_uid', c_uint32),
         ('ssi_fd', c_int32),
         ('ssi_tid', c_uint32),
         ('ssi_band', c_uint32),
         ('ssi_overrun', c_uint32),
         ('ssi_trapno', c_uint32),
         ('ssi_status', c_int32),
         ('ssi_int', c_int32),
         ('ssi_ptr', c_uint64),
         ('ssi_utime', c_uint64),
         ('ssi_stime', c_uint64),
         ('ssi_addr', c_uint64),
         ('__pad', c_uint8 * 48),
     ), [
         '#include <sys/signalfd.h>'
     ]),
    ("""
     typedef union epoll_data {
         void    *ptr;
         int      fd;
         uint32_t u32;
         uint64_t u64;
     } epoll_data_t;
     """,
     'union', 'epoll_data_t', 'epoll_data_t', False, (
         ('ptr', c_voidp),
         ('fd', c_int),
         ('u32', c_uint32),
         ('u64', c_uint64),
     ), [
         '#include <sys/epoll.h>'
     ]),
    ("""
     struct epoll_event {
         uint32_t     events;    /* Epoll events */
         epoll_data_t data;      /* User data variable */
     };
     """,
     'struct', 'epoll_event', 'struct epoll_event', True, (
         ('events', c_uint32),
         ('data', 'glibc.epoll_data_t'),
     ), [
         '#include <sys/epoll.h>'
     ]),
    ("""
     struct itimerspec {
         struct timespec it_interval;  /* Interval for periodic timer */
         struct timespec it_value;     /* Initial expiration */
     };
     """,
     'struct', 'itimerspec', 'struct itimerspec', False, (
         ('it_interval', 'glibc.timespec'),
         ('it_value', 'glibc.timespec'),
     ), [
         '#include <time.h>',
     ]),
    ("""
     struct timespec {
        time_t tv_sec;                /* Seconds */
        long   tv_nsec;               /* Nanoseconds */
     };
     """,
     'struct', 'timespec', 'struct timespec', False, (
         # NOTE: time_t is __TIME_T_TYPE, is __SYSCALL_SLONG_TYPE, is
         # __SQUAD_TYPE, is __quad_t or long it. This is likely not
         # true on !x86_64 but I have to start somewhere.
         #
         # offtopic, I really really think the type proliferation in C is
         # out of control. What would be the problem with having only two
         # types? machine dependent natural word size (same as pointer
         # size), fuck that single exotic 36 bit machine, and a portable
         # collection of fixed-width signed/unsigned types?
         #
         # long, long long, quad and everything else is just meaningless
         # and makes writing portable software harder as nobody knows how
         # to use those types *correctly* and portably to begin with.
         ('tv_sec',     c_long),
         ('tv_nsec',    c_long),
     ), [
         '#include <time.h>',
     ]),
    ("""
     struct timeval {
        time_t      tv_sec;     /* Seconds */
        suseconds_t tv_usec;    /* Microseconds */
     };
     """,
     'struct', 'timeval', 'struct timeval', False, (
         ('tv_sec',     'glibc.time_t'),
         ('tv_usec',    'glibc.suseconds_t'),
     ), [
         '#include <sys/time.h>',
     ]),
]


_glibc_types = [_glibc_typeinfo(*i) for i in _glibc_types]


def _glibc_struct_repr(self):
    return 'struct {} at {:#x}\n'.format(
        self.__class__.__name__, id(self)
    ) + '\n'.join(
        '  {}: {!r}'.format(f_name, getattr(self, f_name))
        for f_name, f_type in self._fields_
    )


def _glibc_type(doc, py_kind, py_name, c_name, c_packed, py_fields, c_macros):
    _globals = {'ctypes': ctypes, 'glibc': _mod}
    py_fields = tuple([
        (py_field_name, (eval(py_field_type, _globals)
                      if isinstance(py_field_type, str)
                      else py_field_type))
        for py_field_name, py_field_type in py_fields
    ])
    if py_kind == 'struct':
        new_type = type(py_name, (ctypes.Structure, ), {
            '__doc__': doc,
            '_fields_': py_fields,
            '_pack_': c_packed,
            '__repr__': _glibc_struct_repr,
        })
    elif py_kind == 'union':
        if c_packed:
            raise ValueError("c_packed is meaningless for unions")
        new_type = type(py_name, (ctypes.Union, ), {
            '__doc__': doc,
            '_fields_': py_fields,
        })
    else:
        raise ValueError("bad value of py_kind")
    return new_type


for info in _glibc_types:
    _mod.lazily(info[2], _glibc_type, info)
del info
# del _glibc_types


_glibc_constantinfo = collections.namedtuple(
    '_glibc_constantinfo', 'name py_ctype py_value c_macros')

# Non-lazily define all supported glibc constants
_glibc_constants = (
    ('NSIG',            c_int, 65, ('#include <signal.h>',)),
    ('SIG_BLOCK',       c_int, 0, ('#include <signal.h>',)),
    ('SIG_UNBLOCK',     c_int, 1, ('#include <signal.h>',)),
    ('SIG_SETMASK',     c_int, 2, ('#include <signal.h>',)),
    ('CLD_EXITED',      c_int, 1, ('#include <signal.h>',)),
    ('CLD_KILLED',      c_int, 2, ('#include <signal.h>',)),
    ('CLD_DUMPED',      c_int, 3, ('#include <signal.h>',)),
    ('CLD_TRAPPED',     c_int, 4, ('#include <signal.h>',)),
    ('CLD_STOPPED',     c_int, 5, ('#include <signal.h>',)),
    ('CLD_CONTINUED',   c_int, 6, ('#include <signal.h>',)),
    ('FD_SETSIZE',      c_int, 1024, ('#include <sys/types.h>',)),
    ('SFD_CLOEXEC',     c_int, 0o2000000, ('#include <sys/signalfd.h>',)),
    ('SFD_NONBLOCK',    c_int, 0o0004000, ('#include <sys/signalfd.h>',)),
    ('EPOLL_CLOEXEC',   c_int, 0o2000000, ('#include <sys/epoll.h>',)),
    # opcodes for epoll_ctl()
    ('EPOLL_CTL_ADD',   c_int, 1, ('#include <sys/epoll.h>',)),
    ('EPOLL_CTL_DEL',   c_int, 2, ('#include <sys/epoll.h>',)),
    ('EPOLL_CTL_MOD',   c_int, 3, ('#include <sys/epoll.h>',)),
    # enum EPOLL_EVENTS
    ('EPOLLIN',         c_uint, 0x0001, ('#include <sys/epoll.h>',)),
    ('EPOLLPRI',        c_uint, 0x0002, ('#include <sys/epoll.h>',)),
    ('EPOLLOUT',        c_uint, 0x0004, ('#include <sys/epoll.h>',)),
    ('EPOLLERR',        c_uint, 0x0008, ('#include <sys/epoll.h>',)),
    ('EPOLLHUP',        c_uint, 0x0010, ('#include <sys/epoll.h>',)),
    ('EPOLLRDNORM',     c_uint, 0x0040, ('#include <sys/epoll.h>',)),
    ('EPOLLRDBAND',     c_uint, 0x0080, ('#include <sys/epoll.h>',)),
    ('EPOLLWRNORM',     c_uint, 0x0100, ('#include <sys/epoll.h>',)),
    ('EPOLLWRBAND',     c_uint, 0x0200, ('#include <sys/epoll.h>',)),
    ('EPOLLMSG',        c_uint, 0x0400, ('#include <sys/epoll.h>',)),
    ('EPOLLRDHUP',      c_uint, 0x2000, ('#include <sys/epoll.h>',)),
    ('EPOLLONESHOT',    c_uint, 1 << 30, ('#include <sys/epoll.h>',)),
    ('EPOLLET',         c_uint, 1 << 31, ('#include <sys/epoll.h>',)),
    # ...
    ('O_CLOEXEC',       c_int, 0o2000000, (
        '#define _POSIX_C_SOURCE 200809L',
        '#include <sys/types.h>',
        '#include <sys/stat.h>',
        '#include <fcntl.h>')),
    ('O_DIRECT',        c_int, 0o0040000, (
        '#define _GNU_SOURCE',
        '#include <sys/types.h>',
        '#include <sys/stat.h>',
        '#include <fcntl.h>')),
    ('O_NONBLOCK',      c_int, 0o00004000, (
        '#define _POSIX_C_SOURCE 200809L',
        '#include <sys/types.h>',
        '#include <sys/stat.h>',
        '#include <fcntl.h>')),
    ('PIPE_BUF',        c_int, 4096, ('#include <limits.h>',)),
    ('PR_SET_PDEATHSIG',            c_int, 1, ('#include <sys/prctl.h>',)),
    ('PR_GET_PDEATHSIG',            c_int, 2, ('#include <sys/prctl.h>',)),
    ('PR_GET_DUMPABLE',             c_int, 3, ('#include <sys/prctl.h>',)),
    ('PR_SET_DUMPABLE',             c_int, 4, ('#include <sys/prctl.h>',)),
    ('PR_GET_UNALIGN',              c_int, 5, ('#include <sys/prctl.h>',)),
    ('PR_SET_UNALIGN',              c_int, 6, ('#include <sys/prctl.h>',)),
    ('PR_GET_KEEPCAPS',             c_int, 7, ('#include <sys/prctl.h>',)),
    ('PR_SET_KEEPCAPS',             c_int, 8, ('#include <sys/prctl.h>',)),
    ('PR_GET_FPEMU',                c_int, 9, ('#include <sys/prctl.h>',)),
    ('PR_SET_FPEMU',                c_int, 10, ('#include <sys/prctl.h>',)),
    ('PR_GET_FPEXC',                c_int, 11, ('#include <sys/prctl.h>',)),
    ('PR_SET_FPEXC',                c_int, 12, ('#include <sys/prctl.h>',)),
    ('PR_GET_TIMING',               c_int, 13, ('#include <sys/prctl.h>',)),
    ('PR_SET_TIMING',               c_int, 14, ('#include <sys/prctl.h>',)),
    ('PR_SET_NAME',                 c_int, 15, ('#include <sys/prctl.h>',)),
    ('PR_GET_NAME',                 c_int, 16, ('#include <sys/prctl.h>',)),
    ('PR_GET_ENDIAN',               c_int, 19, ('#include <sys/prctl.h>',)),
    ('PR_SET_ENDIAN',               c_int, 20, ('#include <sys/prctl.h>',)),
    ('PR_GET_SECCOMP',              c_int, 21, ('#include <sys/prctl.h>',)),
    ('PR_SET_SECCOMP',              c_int, 22, ('#include <sys/prctl.h>',)),
    ('PR_CAPBSET_READ',             c_int, 23, ('#include <sys/prctl.h>',)),
    ('PR_CAPBSET_DROP',             c_int, 24, ('#include <sys/prctl.h>',)),
    ('PR_GET_TSC',                  c_int, 25, ('#include <sys/prctl.h>',)),
    ('PR_SET_TSC',                  c_int, 26, ('#include <sys/prctl.h>',)),
    ('PR_GET_SECUREBITS',           c_int, 27, ('#include <sys/prctl.h>',)),
    ('PR_SET_SECUREBITS',           c_int, 28, ('#include <sys/prctl.h>',)),
    ('PR_SET_TIMERSLACK',           c_int, 29, ('#include <sys/prctl.h>',)),
    ('PR_GET_TIMERSLACK',           c_int, 30, ('#include <sys/prctl.h>',)),
    ('PR_TASK_PERF_EVENTS_DISABLE', c_int, 31, ('#include <sys/prctl.h>',)),
    ('PR_TASK_PERF_EVENTS_ENABLE',  c_int, 32, ('#include <sys/prctl.h>',)),
    ('PR_MCE_KILL',                 c_int, 33, ('#include <sys/prctl.h>',)),
    ('PR_MCE_KILL_GET',             c_int, 34, ('#include <sys/prctl.h>',)),
    ('PR_SET_MM',                   c_int, 35, ('#include <sys/prctl.h>',)),
    ('PR_SET_CHILD_SUBREAPER',      c_int, 36, ('#include <sys/prctl.h>',)),
    ('PR_GET_CHILD_SUBREAPER',      c_int, 37, ('#include <sys/prctl.h>',)),
    ('PR_SET_NO_NEW_PRIVS',         c_int, 38, ('#include <sys/prctl.h>',)),
    ('PR_GET_NO_NEW_PRIVS',         c_int, 39, ('#include <sys/prctl.h>',)),
    ('PR_GET_TID_ADDRESS',          c_int, 40, ('#include <sys/prctl.h>',)),
    ('PR_SET_THP_DISABLE',          c_int, 41, ('#include <sys/prctl.h>',)),
    ('PR_GET_THP_DISABLE',          c_int, 42, ('#include <sys/prctl.h>',)),
    ('PR_UNALIGN_NOPRINT',          c_int, 1, ('#include <sys/prctl.h>',)),
    ('PR_UNALIGN_SIGBUS',           c_int, 2, ('#include <sys/prctl.h>',)),
    ('PR_FPEMU_NOPRINT',            c_int, 1, ('#include <sys/prctl.h>',)),
    ('PR_FPEMU_SIGFPE',             c_int, 2, ('#include <sys/prctl.h>',)),
    ('PR_FP_EXC_SW_ENABLE',         c_int, 0x80, ('#include <sys/prctl.h>',)),
    ('PR_FP_EXC_DIV',               c_int, 0x010000, (
        '#include <sys/prctl.h>',)),
    ('PR_FP_EXC_OVF',               c_int, 0x020000, (
        '#include <sys/prctl.h>',)),
    ('PR_FP_EXC_UND',               c_int, 0x040000, (
        '#include <sys/prctl.h>',)),
    ('PR_FP_EXC_RES',               c_int, 0x080000, (
        '#include <sys/prctl.h>',)),
    ('PR_FP_EXC_INV',               c_int, 0x100000, (
        '#include <sys/prctl.h>',)),
    ('PR_FP_EXC_DISABLED',          c_int, 0, ('#include <sys/prctl.h>',)),
    ('PR_FP_EXC_NONRECOV',          c_int, 1, ('#include <sys/prctl.h>',)),
    ('PR_FP_EXC_ASYNC',             c_int, 2, ('#include <sys/prctl.h>',)),
    ('PR_FP_EXC_PRECISE',           c_int, 3, ('#include <sys/prctl.h>',)),
    ('PR_TIMING_STATISTICAL',       c_int, 0, ('#include <sys/prctl.h>',)),
    ('PR_TIMING_TIMESTAMP',         c_int, 1, ('#include <sys/prctl.h>',)),
    ('PR_ENDIAN_BIG',               c_int, 0, ('#include <sys/prctl.h>',)),
    ('PR_ENDIAN_LITTLE',            c_int, 1, ('#include <sys/prctl.h>',)),
    ('PR_ENDIAN_PPC_LITTLE',        c_int, 2, ('#include <sys/prctl.h>',)),
    ('PR_TSC_ENABLE',               c_int, 1, ('#include <sys/prctl.h>',)),
    ('PR_TSC_SIGSEGV',              c_int, 2, ('#include <sys/prctl.h>',)),
    ('PR_MCE_KILL_CLEAR',           c_int, 0, ('#include <sys/prctl.h>',)),
    ('PR_MCE_KILL_SET',             c_int, 1, ('#include <sys/prctl.h>',)),
    ('PR_MCE_KILL_LATE',            c_int, 0, ('#include <sys/prctl.h>',)),
    ('PR_MCE_KILL_EARLY',           c_int, 1, ('#include <sys/prctl.h>',)),
    ('PR_MCE_KILL_DEFAULT',         c_int, 2, ('#include <sys/prctl.h>',)),
    ('PR_SET_MM_START_CODE',        c_int, 1, ('#include <sys/prctl.h>',)),
    ('PR_SET_MM_END_CODE',          c_int, 2, ('#include <sys/prctl.h>',)),
    ('PR_SET_MM_START_DATA',        c_int, 3, ('#include <sys/prctl.h>',)),
    ('PR_SET_MM_END_DATA',          c_int, 4, ('#include <sys/prctl.h>',)),
    ('PR_SET_MM_START_STACK',       c_int, 5, ('#include <sys/prctl.h>',)),
    ('PR_SET_MM_START_BRK',         c_int, 6, ('#include <sys/prctl.h>',)),
    ('PR_SET_MM_BRK',               c_int, 7, ('#include <sys/prctl.h>',)),
    ('PR_SET_MM_ARG_START',         c_int, 8, ('#include <sys/prctl.h>',)),
    ('PR_SET_MM_ARG_END',           c_int, 9, ('#include <sys/prctl.h>',)),
    ('PR_SET_MM_ENV_START',         c_int, 10, ('#include <sys/prctl.h>',)),
    ('PR_SET_MM_ENV_END',           c_int, 11, ('#include <sys/prctl.h>',)),
    ('PR_SET_MM_AUXV',              c_int, 12, ('#include <sys/prctl.h>',)),
    ('PR_SET_MM_EXE_FILE',          c_int, 13, ('#include <sys/prctl.h>',)),
    ('PR_SET_PTRACER',              c_int, 0x59616d61, (
        '#include <sys/prctl.h>',)),
    ('PR_SET_PTRACER_ANY',          c_ulong, -1, ('#include <sys/prctl.h>',)),
    ('TFD_TIMER_ABSTIME',           c_int, 1, ('#include <sys/timerfd.h>',)),
    ('TFD_CLOEXEC',                 c_int, 0o2000000, (
        '#include <sys/timerfd.h>',)),
    ('TFD_NONBLOCK',                c_int, 0o0004000, (
        '#include <sys/timerfd.h>',)),
    ('EFD_CLOEXEC',     c_int, 0o2000000,   ('#include <sys/eventfd.h>',)),
    ('EFD_NONBLOCK',    c_int, 0o0004000,   ('#include <sys/eventfd.h>',)),
    ('EFD_SEMAPHORE',   c_int, 1,           ('#include <sys/eventfd.h>',)),
    ('CLOCK_REALTIME',              c_int,  0,  ('#include <time.h>',)),
    ('CLOCK_MONOTONIC',             c_int,  1,  ('#include <time.h>',)),
    ('CLOCK_PROCESS_CPUTIME_ID',    c_int,  2,  ('#include <time.h>',)),
    ('CLOCK_THREAD_CPUTIME_ID',     c_int,  3,  ('#include <time.h>',)),
    ('CLOCK_MONOTONIC_RAW',         c_int,  4,  ('#include <time.h>',)),
    ('CLOCK_REALTIME_COARSE',       c_int,  5,  ('#include <time.h>',)),
    ('CLOCK_MONOTONIC_COARSE',      c_int,  6,  ('#include <time.h>',)),
    ('CLOCK_BOOTTIME',              c_int,  7,  ('#include <time.h>',)),
    ('CLOCK_REALTIME_ALARM',        c_int,  8,  ('#include <time.h>',)),
    ('CLOCK_BOOTTIME_ALARM',        c_int,  9,  ('#include <time.h>',)),
    # fcntl(2) codes
    ('F_SETPIPE_SZ',                c_int,  1031, (
        '#define _GNU_SOURCE',
        '#include <unistd.h>',
        '#include <fcntl.h>',)),
    ('F_GETPIPE_SZ',                c_int,  1032, (
        '#define _GNU_SOURCE',
        '#include <unistd.h>',
        '#include <fcntl.h>',)),
)


_glibc_constants = [_glibc_constantinfo(*i) for i in _glibc_constants]


for info in _glibc_constants:
    _mod.immediate(info.name, info.py_value)
del info
# del _glibc_constants


# Lazily define all supported glibc functions
_glibc_functions = (
    ('sigemptyset', c_int, ['ctypes.POINTER(glibc.sigset_t)'],
     """int sigemptyset(sigset_t *set);""",
     -1, {
         errno.EINVAL: "sig is not a valid signal"
     }),
    ('sigfillset', c_int, ['ctypes.POINTER(glibc.sigset_t)'],
     """int sigfillset(sigset_t *set);""",
     -1, {
         errno.EINVAL: "sig is not a valid signal"
     }),
    ('sigaddset', c_int, ['ctypes.POINTER(glibc.sigset_t)', c_int],
     """int sigaddset(sigset_t *set, int signum);""",
     -1, {
         errno.EINVAL: "sig is not a valid signal"
     }),
    ('sigdelset', c_int, ['ctypes.POINTER(glibc.sigset_t)', c_int],
     """int sigdelset(sigset_t *set, int signum);""",
     -1, {
         errno.EINVAL: "sig is not a valid signal"
     }),
    ('sigismember', c_int, ['ctypes.POINTER(glibc.sigset_t)', c_int],
     """int sigismember(sigset_t *set, int signum);""",
     -1, {
         errno.EINVAL: "sig is not a valid signal"
     }),
    ('sigprocmask', c_int, [c_int, 'ctypes.POINTER(glibc.sigset_t)',
                            'ctypes.POINTER(glibc.sigset_t)'],
     """int sigprocmask(int how, const sigset_t *set, sigset_t *oldset);""",
     -1, {
         errno.EFAULT: ("The ``set`` or ``oldset`` arguments points outside"
                        " of the process's address space"),
         errno.EINVAL: "The value specified in ``how`` was invalid",
     }),
    ('pthread_sigmask', c_int, [c_int, 'ctypes.POINTER(glibc.sigset_t)',
                                'ctypes.POINTER(glibc.sigset_t)'],
     """int pthread_sigmask(int how, const sigset_t *set, sigset_t *oldset);"""
     'pthread', {
         errno.EFAULT: ("The ``set`` or ``oldset`` arguments points outside"
                        " of the process's address space"),
         errno.EINVAL: "The value specified in ``how`` was invalid",
     }),
    ('signalfd', c_int, [c_int, 'ctypes.POINTER(glibc.sigset_t)', c_int],
     """int signalfd(int fd, const sigset_t *mask, int flags);""",
     -1, {
         errno.EBADF: "The fd file descriptor is not a valid file descriptor",
         errno.EINVAL: ("fd is not a valid signalfd file descriptor; "
                        "flags is invalid; "
                        "in Linux 2.6.26 or earlier, flags is nonzero"),
         errno.EMFILE: ("The per-process limit of open file descriptors has"
                        " been reached"),
         errno.ENFILE: ("The system-wide limit on the total number of open",
                        " file descriptors has been reached"),
         errno.ENODEV: ("Could not mount (internal) anonymous inode device"),
         errno.ENOMEM: ("There was insufficient memory to create a new"
                        " signalfd file descriptor")
     }),
    ('epoll_create', c_int, [c_int],
     """int epoll_create(int size);""",
     -1, {
         errno.EINVAL: "size is not positive.",
         errno.EMFILE: ("The per-user limit on the number of epoll instances"
                        " imposed by /proc/sys/fs/epoll/max_user_instances was"
                        " encountered.  See epoll(7) for further details."),
         errno.ENFILE: ("The system limit on the total number of open files"
                        " has been reached."),
         errno.ENOMEM: ("There was insufficient memory to create the kernel"
                        " object."),
     }),
    ('epoll_create1', c_int, [c_int],
     """int epoll_create1(int flags);""",
     -1, {
         errno.EINVAL: "Invalid value specified in flags.",
         errno.EMFILE: ("The per-user limit on the number of epoll instances"
                        " imposed by /proc/sys/fs/epoll/max_user_instances was"
                        " encountered.  See epoll(7) for further details."),
         errno.ENFILE: ("The system limit on the total number of open files"
                        " has been reached."),
         errno.ENOMEM: ("There was insufficient memory to create the kernel"
                        " object."),
     }),
    ('epoll_wait', c_int, [c_int, 'ctypes.POINTER(glibc.epoll_event)', c_int,
                           c_int],
     """int epoll_wait(int epfd, struct epoll_event *events,
                       int maxevents, int timeout);""",
     -1, {
         errno.EBADF: "epfd is not a valid file descriptor.",
         errno.EFAULT: ("The memory area pointed to by events is not"
                        " accessible with write permissions."),
         errno.EINTR: ("The call was interrupted by a signal handler before"
                       " either (1) any of the requested events occurred"
                       " or (2) the timeout expired; see signal(7)."),
         errno.EINVAL: ("epfd is not an epoll file descriptor, or maxevents"
                        " is less than or equal to zero."),
     }),
    ('epoll_pwait', c_int, [c_int, 'ctypes.POINTER(glibc.epoll_event)', c_int,
                            c_int, 'ctypes.POINTER(glibc.sigset_t)'],
     """int epoll_pwait(int epfd, struct epoll_event *events,
                        int maxevents, int timeout,
                        const sigset_t *sigmask);""",
     -1, {
         errno.EBADF: "epfd is not a valid file descriptor.",
         errno.EFAULT: ("The memory area pointed to by events is not"
                        " accessible with write permissions."),
         errno.EINTR: ("The call was interrupted by a signal handler before"
                       " either (1) any of the requested events occurred"
                       " or (2) the timeout expired; see signal(7)."),
         errno.EINVAL: ("epfd is not an epoll file descriptor, or maxevents"
                        " is less than or equal to zero."),
     }),
    ('epoll_ctl', c_int, [c_int, c_int, c_int,
                          'ctypes.POINTER(glibc.epoll_event)'],
     "int epoll_ctl(int epfd, int op, int fd, struct epoll_event *event);",
     -1, {
         errno.EBADF: "epfd or fd is not a valid file descriptor.",
         errno.EEXIST: ("op was EPOLL_CTL_ADD, and the supplied file"
                        " descriptor fd is already registered with this"
                        " epoll instance."),
         errno.EINVAL: ("epfd is not an epoll file descriptor, or fd is the"
                        " same as epfd, or the requested operation op is not"
                        " supported by this interface."),
         errno.ENOENT: ("op was EPOLL_CTL_MOD or EPOLL_CTL_DEL, and fd is not"
                        " registered with this epoll instance."),
         errno.ENOMEM: ("There was insufficient memory to handle the requested"
                        " op control operation."),
         errno.ENOSPC: ("The limit imposed by"
                        " /proc/sys/fs/epoll/max_user_watches was encountered"
                        " while trying to register (EPOLL_CTL_ADD) a new file"
                        " descriptor on an epoll instance. See epoll(7) for"
                        " further details."),
         errno.EPERM: "The target file fd does not support epoll.",
     }),
    ('pipe', c_int, [POINTER(c_int * 2)],
     """int pipe2(int pipefd[2], int flags);""",
     -1, {
         errno.EFAULT: "pipefd is not valid.",
         errno.EMFILE: "Too many file descriptors are in use by the process.",
         errno.ENFILE: ("The system limit on the total number of open files"
                        " has been reached."),
     }),
    ('pipe2', c_int, [POINTER(c_int * 2), c_int],
     """int pipe2(int pipefd[2], int flags);""",
     -1, {
         errno.EFAULT: "pipefd is not valid.",
         errno.EINVAL: "Invalid value in flags.",
         errno.EMFILE: "Too many file descriptors are in use by the process.",
         errno.ENFILE: ("The system limit on the total number of open files"
                        " has been reached."),
     }),
    ('dup', c_int, [c_int],
     """int dup(int oldfd);""",
     -1, {
         errno.EBADF: ("oldfd isn't an open file descriptor, or newfd is out"
                       " of the allowed range for file descriptors."),
         errno.EMFILE: ("The process already has the maximum number of file"
                        " descriptors open and tried to open a new one."),
     }),
    ('dup2', c_int, [c_int, c_int],
     """int dup2(int oldfd, int newfd);""",
     -1, {
         errno.EBADF: ("oldfd isn't an open file descriptor, or newfd is out"
                       " of the allowed range for file descriptors."),
         errno.EBUSY: ("(Linux only) This may be returned by dup2() or dup3()"
                       " during a race condition with open(2) and dup()."),
         errno.EINTR: ("The dup2() or dup3() call was interrupted by a signal;"
                       " see signal(7)."),
         errno.EMFILE: ("The process already has the maximum number of file"
                        " descriptors open and tried to open a new one."),
     }),
    ('dup3', c_int, [c_int, c_int, c_int],
     """int dup3(int oldfd, int newfd, int flags);""",
     -1, {
         errno.EBADF: ("oldfd isn't an open file descriptor, or newfd is out"
                       " of the allowed range for file descriptors."),
         errno.EBUSY: ("(Linux only) This may be returned by dup2() or dup3()"
                       " during a race condition with open(2) and dup()."),
         errno.EINTR: ("The dup2() or dup3() call was interrupted by a signal;"
                       " see signal(7)."),
         errno.EINVAL: ("(dup3()) flags contain an invalid value.  Or, oldfd"
                        " was equal to newfd."),
         errno.EMFILE: ("The process already has the maximum number of file"
                        " descriptors open and tried to open a new one."),
     }),
    ('read', c_ssize_t, [c_int, c_voidp, c_size_t],
     """ssize_t read(int fd, void *buf, size_t count);""",
     -1, {
         EAGAIN: (
             "The file descriptor fd refers to a file other than a socket"
             " and has been marked nonblocking (O_NONBLOCK), and the read"
             " would block."),
         EWOULDBLOCK: '\n'.join([(
             "The file descriptor fd refers to a file other than a socket"
             " and has been marked nonblocking (O_NONBLOCK), and the read"
             " would block."
         ), (
             "The file descriptor fd refers to a socket and has been marked"
             " nonblocking (O_NONBLOCK), and the read would block."
             " POSIX.1-2001 allows either EAGAIN or EWOULDBLOCK error to be"
             " returned for this case, and does not require these constants"
             " to have the same value, so a portable application should"
             " check for both possibilities.")]),
         EBADF: (
             "fd is not a valid file descriptor or is not open for reading."),
         EFAULT: (
             "buf is outside your accessible address space."),
         EINTR: (
             "The call was interrupted by a signal before any data was read;"
             " see signal(7)."),
         EINVAL: '\n'.join([(
             "fd is attached to an object which is unsuitable for reading;"
             " or the file was opened with the O_DIRECT flag, and either the"
             " address specified in buf, the value specified in count, or"
             " the current file offset is not suitably aligned."
         ), (
             "fd was created via a call to timerfd_create(2) and the wrong"
             " size buffer was given to read(); see timerfd_create(2) for"
             " further information.")]),
         EIO: (
             "I/O error. This will happen for example when the process is in"
             " a background process group, tries to read from its controlling"
             " terminal, and either it is ignoring or blocking SIGTTIN or"
             " its process group is orphaned. It may also occur when there is"
             " a low-level I/O error while reading from a disk or tape."),
         EISDIR: (
             "fd refers to a directory.")
     }),
    ('close', c_int, [c_int],
     """int close(int fd);""",
     -1, {
         errno.EBADF: "fd isn't a valid open file descriptor.",
         errno.EINTR: ("The close() call was interrupted by a signal;"
                       " see signal(7)."),
         errno.EIO: "An I/O error occurred."
     }),
    ('prctl', c_int, [c_int, c_ulong, c_ulong, c_ulong, c_ulong],
     """int prctl(int option, unsigned long arg2, unsigned long arg3,
                  unsigned long arg4, unsigned long arg5);""",
     -1, {
         EFAULT: "arg2 is an invalid address.",
         EINVAL: '\n'.join([
             ("The value of option is not recognized."),
             ("option is PR_MCE_KILL or PR_MCE_KILL_GET or PR_SET_MM,"
              " and unused prctl() arguments were not specified as zero."),
             ("arg2 is not valid value for this option."),
             ("option is PR_SET_SECCOMP or PR_GET_SECCOMP, and the kernel"
              " was not configured with CONFIG_SECCOMP."),
             ("option is PR_SET_MM, and one of the following is true:\n"
              " * arg4 or arg5 is nonzero;\n"
              " * arg3 is greater than TASK_SIZE (the limit on the size\n"
              "   of the user  address  space  for this architecture);\n"
              " * arg2 is PR_SET_MM_START_CODE, PR_SET_MM_END_CODE,\n"
              "   PR_SET_MM_START_DATA, PR_SET_MM_END_DATA,\n"
              "   or PR_SET_MM_START_STACK, and the permissions\n"
              "   of the corresponding memory area are not as required;\n"
              " * arg2 is PR_SET_MM_START_BRK or PR_SET_MM_BRK, and arg3\n"
              "   is less than or equal to the end of the data segment\n"
              "   or specifies a value that would cause the RLIMIT_DATA\n"
              "   resource limit to be exceeded."),
             ("option is PR_SET_PTRACER and arg2 is not 0,"
              " PR_SET_PTRACER_ANY, or the PID of an existing process."),
             ("option is PR_SET_PDEATHSIG and arg2 is not a valid signal"
              " number."),
             ("option is PR_SET_DUMPABLE and arg2 is neither"
              " SUID_DUMP_DISABLE nor SUID_DUMP_USER.\n"),
             ("option is PR_SET_TIMING and arg2 is not"
              " PR_TIMING_STATISTICAL."),
             ("option is PR_SET_NO_NEW_PRIVS and arg2 is not equal to 1"
              " or arg3, arg4, or arg5 is nonzero."),
             ("option is PR_GET_NO_NEW_PRIVS and arg2, arg3, arg4,"
              " or arg5 is nonzero."),
             ("option is PR_SET_THP_DISABLE and arg3, arg4,"
              " or arg5 is nonzero."),
             ("option is PR_GET_THP_DISABLE and arg2, arg3, arg4,"
              " or arg5 is nonzero.")
         ]),
         EPERM: '\n'.join([
             ("option is PR_SET_SECUREBITS, and the caller does not have the"
              " CAP_SETPCAP capability, or tried to unset a \"locked\" flag,"
              " or tried to set a flag whose corresponding locked  flag was"
              " set (see capabilities(7))."),
             ("option is PR_SET_KEEPCAPS, and the callers's"
              " SECURE_KEEP_CAPS_LOCKED flag is set (see capabilities(7))."),
             ("option is PR_CAPBSET_DROP, and the caller does not have"
              " the CAP_SETPCAP capability."),
             ("option is PR_SET_MM, and the caller does not have"
              " the CAP_SYS_RESOURCE capability.")
         ]),
         EACCES: ("option is PR_SET_MM, and arg3 is PR_SET_MM_EXE_FILE,"
                  " the file is not executable."),
         EBUSY: ("option is PR_SET_MM, arg3 is PR_SET_MM_EXE_FILE, and this"
                 " the second attempt to change the /proc/pid/exe symbolic"
                 " link, which is prohibited."),
         EBADF: ("option  is  PR_SET_MM, arg3 is PR_SET_MM_EXE_FILE,"
                 " and the file descriptor passed in arg4 is not valid."),
     }),
    ('timerfd_create', c_int, [c_int, c_int],
     """int timerfd_create(int clockid, int flags);""",
     -1, {
     }),
    ('timerfd_settime', c_int, [c_int, c_int,
                                'ctypes.POINTER(glibc.itimerspec)',
                                'ctypes.POINTER(glibc.itimerspec)'],
     """int timerfd_settime(int fd, int flags,
                            const struct itimerspec *new_value,
                            struct itimerspec *old_value);""",
     -1, {
     }),
    ('timerfd_gettime', c_int, [c_int, 'ctypes.POINTER(glibc.itimerspec)'],
     """int timerfd_gettime(int fd, struct itimerspec *curr_value);""",
     -1, {
     }),
    ('pause', c_int, [],
     """int pause();""", -1, {
         EINTR: (
             "a signal was caught and the signal-catching function returned."
         )
     }),
    ('eventfd', c_int, [c_uint, c_int],
     """int eventfd(unsigned int initval, int flags);""", -1, {
         EINVAL: (
             "An unsupported value was specified in flags."),
         EMFILE: (
             "The per-process limit on open file descriptors has been"
             " reached."),
         ENFILE: (
             "The system-wide limit on the total number of open files has"
             " been reached."),
         ENODEV: (
             "Could not mount (internal) anonymous inode device."),
         ENOMEM: (
             "There was insufficient memory to create a new eventfd file"
             " descriptor."),
     }),
    ('eventfd_read', c_int, [c_uint, 'ctypes.POINTER(glibc.eventfd_t)'],
     """int eventfd_read(int fd, eventfd_t *value);""", -1, {}),
    ('eventfd_write', c_int, [c_uint, 'glibc.eventfd_t'],
     """int eventfd_write(int fd, eventfd_t value);""", -1, {}),
    ('clock_getres', c_int, ['glibc.clockid_t',
                             'ctypes.POINTER(glibc.timespec)'],
     """int clock_getres(clockid_t clk_id, struct timespec *res);""", -1, {
         EFAULT: (
             "res points outside the accessible address space."),
         EINVAL: (
             "The clk_id specified is not supported on this system."),
     }),
    ('clock_gettime', c_int, ['glibc.clockid_t',
                              'ctypes.POINTER(glibc.timespec)'],
     """int clock_gettime(clockid_t clk_id, struct timespec *tp);""", -1, {
         EFAULT: (
             "tp points outside the accessible address space."),
         EINVAL: (
             "The clk_id specified is not supported on this system."),
     }),
    ('clock_settime', c_int, ['glibc.clockid_t',
                              'ctypes.POINTER(glibc.timespec)'],
     """int clock_settime(clockid_t clk_id, const struct timespec *tp);""",
     -1, {
         EFAULT: (
             "tp points outside the accessible address space."),
         EINVAL: (
             "The clk_id specified is not supported on this system."),
         EPERM: (
             "clock_settime() does not have permission to set the clock"
             " indicated."),
     }),
)


def _glibc_func(name, restype, argtypes, doc,
                error_result=None, errno_map=None):
    if name.startswith('pthread_'):
        func = getattr(_pthread, name)
    else:
        func = getattr(_glibc, name)
    _globals = {'ctypes': ctypes, 'glibc': _mod}
    func.argtypes = [
        eval(argtype, _globals) if isinstance(argtype, str) else argtype
        for argtype in argtypes
    ]
    func.restype = (
        eval(restype, _globals) if isinstance(restype, str) else restype)
    if errno_map is not None and error_result == 'pthread':
        # Use a variant of error-code to errno translator that is specific
        # to pthread_* family of functions that don't touch errno
        def pthread_errcheck(result, func, arguments):
            if result != 0:
                raise OSError(result, errno_map.get(
                    result, os.strerror(result)))
            return result
        func.errcheck = pthread_errcheck
    elif errno_map is not None:
        # Use built-in error-code to errno translator
        def std_errcheck(result, func, arguments):
            if result == error_result:
                errno = get_errno()
                raise OSError(errno, errno_map.get(errno, os.strerror(errno)))
            return result
        func.errcheck = std_errcheck
    return func


for info in _glibc_functions:
    _mod.lazily(info[0], _glibc_func, info)
del info
del _glibc_functions
