#
# This file is part of Checkbox.
#
# Copyright 2008 Canonical Ltd.
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
#
import re

from datetime import (
    datetime,
    timedelta,
    )

from checkbox_support.lib.tz import tzutc


DATETIME_RE = re.compile(r"""
    ^(?P<year>\d\d\d\d)-?(?P<month>\d\d)-?(?P<day>\d\d)
    T(?P<hour>\d\d):?(?P<minute>\d\d):?(?P<second>\d\d)
    (?:\.(?P<second_fraction>\d{0,6}))?
    (?P<tz>
        (?:(?P<tz_sign>[-+])(?P<tz_hour>\d\d):(?P<tz_minute>\d\d))
        | Z)?$
    """, re.VERBOSE)

TYPE_FORMATS = (
    (r"(yes|true)", lambda v: True),
    (r"(no|false)", lambda v: False),
    (r"-?\d+", lambda v: int(v.group(0))),
    (r"-?\d+\.\d+", lambda v: float(v.group(0))),
    (r"(-?\d+) ?([kmgt]?b?)", lambda v: int(v.group(1))),
    (r"(-?\d+\.\d+) ?([kmgt]?b?)", lambda v: float(v.group(1))),
    (r"(-?\d+) ?([kmgt]?hz)", lambda v: int(v.group(1))),
    (r"(-?\d+\.\d+) ?([kmgt]?hz)", lambda v: float(v.group(1))))
TYPE_FORMATS = tuple(
    (re.compile(r"^%s$" % pattern, re.IGNORECASE), format)
    for pattern, format in TYPE_FORMATS)

TYPE_MULTIPLIERS = (
    (r"b", 1),
    (r"kb?", 1024),
    (r"mb?", 1024 * 1024),
    (r"gb?", 1024 * 1024 * 1024),
    (r"tb?", 1024 * 1024 * 1024 * 1024),
    (r"hz", 1),
    (r"khz?", 1024),
    (r"mhz?", 1024 * 1024),
    (r"ghz?", 1024 * 1024 * 1024),
    (r"thz?", 1024 * 1024 * 1024 * 1024))
TYPE_MULTIPLIERS = tuple(
    (re.compile(r"^%s$" % pattern, re.IGNORECASE), multiplier)
    for pattern, multiplier in TYPE_MULTIPLIERS)


def datetime_to_string(dt):
    """Return a consistent string representation for a given datetime.

    :param dt: The datetime object.
    """
    return dt.isoformat()


def string_to_datetime(string):
    """Return a datetime object from a consistent string representation.

    :param string: The string representation.
    """
    # we cannot use time.strptime: this function accepts neither fractions
    # of a second nor a time zone given e.g. as '+02:30'.
    match = DATETIME_RE.match(string)

    # The Relax NG schema allows a leading minus sign and year numbers
    # with more than four digits, which are not "covered" by _time_regex.
    if not match:
        raise ValueError("Datetime with unreasonable value: %s" % string)

    time_parts = match.groupdict()

    year = int(time_parts['year'])
    month = int(time_parts['month'])
    day = int(time_parts['day'])
    hour = int(time_parts['hour'])
    minute = int(time_parts['minute'])
    second = int(time_parts['second'])
    second_fraction = time_parts['second_fraction']
    if second_fraction is not None:
        milliseconds = second_fraction + '0' * (6 - len(second_fraction))
        milliseconds = int(milliseconds)
    else:
        milliseconds = 0

    # The Relax NG validator accepts leap seconds, but the datetime
    # constructor rejects them. The time values submitted by the HWDB
    # client are not necessarily very precise, hence we can round down
    # to 59.999999 seconds without losing any real precision.
    if second > 59:
        second = 59
        milliseconds = 999999

    dt = datetime(
        year, month, day, hour, minute, second, milliseconds, tzinfo=tzutc)

    tz_sign = time_parts['tz_sign']
    tz_hour = time_parts['tz_hour']
    tz_minute = time_parts['tz_minute']
    if tz_sign in ('-', '+'):
        delta = timedelta(hours=int(tz_hour), minutes=int(tz_minute))
        if tz_sign == '-':
            dt = dt + delta
        else:
            dt = dt - delta

    return dt


def sizeof_bytes(bytes):
    for x in ["bytes", "KB", "MB", "GB", "TB"]:
        string = "%3.1f%s" % (bytes, x)
        if bytes < 1024.0:
            break
        bytes /= 1024.0

    return string


def sizeof_hertz(hertz):
    for x in ["Hz", "KHz", "MHz", "GHz"]:
        string = "%3.1f%s" % (hertz, x)
        if hertz < 1000.0:
            break
        hertz /= 1000.0

    return string


def string_to_type(string):
    """Return a typed representation for the given string.

    The result might be a bool, int or float. The string might also be
    supplemented by a multiplier like KB which would return an int or
    float multiplied by 1024 for example.

    :param string: The string representation.
    """
    for regex, formatter in TYPE_FORMATS:
        match = regex.match(string)
        if match:
            string = formatter(match)
            if len(match.groups()) > 1:
                unit = match.group(2)
                for regex, multiplier in TYPE_MULTIPLIERS:
                    match = regex.match(unit)
                    if match:
                        string *= multiplier
                        break
                else:
                    raise ValueError("Unknown multiplier: %s" % unit)
            break

    return string
