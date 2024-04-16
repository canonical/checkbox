# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.

#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
:mod:`plainbox.impl.session` -- session handling
================================================

Sessions are central state holders and one of the most important classes in
PlainBox. Since they are all named alike it's a bit hard to find what the
actual responsibilities are. Here's a small shortcut, do read the description
of each module and class for additional details though.


:class:`SessionState`

    This a class that holds all of the state and program logic. It
    :class:`SessionManager` is a class that couples :class:`SessionState` and
    :class:`SessionStorage`. It has the methods required to alter the state by
    introducing additional jobs or results. It's main responsibility is to keep
    track of all of the jobs, their results, if they are runnable or not
    (technically what is preventing them from being runnable) and to compute
    the order of execution that can satisfy all of the dependencies.

    It holds a number of references to other pieces of PlainBox (jobs,
    resources and other things) but one thing stands out. This class holds
    references to a number of :class:`JobState` objects that couple a
    :class:`JobResult` and :class:`JobDefinition` together.

:class:`JobState`

    A coupling class between :class:`JobDefinition` and :class:`JobResult`.
    This class also knows why a job cannot be started in a particular session,
    by maintaining a set of "inhibitors" that prevent it from being runnable.
    The actual inhibitors are managed by :class:`SessionState`.

:class:`SessionStorage`

    This class knows how properly to save and load bytes and manages a
    directory for all the filesystem entries associated with a particular
    session. It holds no references to a session though.
"""

from plainbox.impl.session.jobs import InhibitionCause
from plainbox.impl.session.jobs import JobReadinessInhibitor
from plainbox.impl.session.jobs import JobState
from plainbox.impl.session.jobs import UndesiredJobReadinessInhibitor
from plainbox.impl.session.manager import SessionManager
from plainbox.impl.session.resume import SessionPeekHelper
from plainbox.impl.session.resume import SessionResumeError
from plainbox.impl.session.state import SessionMetaData
from plainbox.impl.session.state import SessionState
from plainbox.impl.session.storage import SessionStorage

__all__ = (
    "JobReadinessInhibitor",
    "JobState",
    "SessionManager",
    "SessionMetaData",
    "SessionPeekHelper",
    "SessionResumeError",
    "SessionState",
    "SessionStorage",
    "UndesiredJobReadinessInhibitor",
    "InhibitionCause",
)
