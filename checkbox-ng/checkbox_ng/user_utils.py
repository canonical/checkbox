"""
This modules has utilities to handle information about users available in the
system.
"""

import logging
import pwd

from contextlib import suppress

_logger = logging.getLogger("checkbox_ng.user_utils")


def check_user_exists(user: str) -> bool:
    """
    Check if a user exists in the system.

    :param str user: The username to check.
    :return: True if the user exists, False otherwise.
    :rtype: bool
    :raises TypeError: If the input is not a string.
    """
    try:
        pwd.getpwnam(user)
        return True
    except KeyError:
        return False


def guess_normal_user() -> str:
    """
    Guess the normal user in the system by checking for specific users
    and UIDs.

    This function first checks if the 'ubuntu' user exists in the system.
    If not found, it tries to find a user with UID 1000.
    If still not found, it tries to find a user with UID 1001.

    :return: The username of the guessed normal user.
    :rtype: str
    """
    for entry in pwd.getpwall():
        if entry.pw_name == "ubuntu":
            _logger.warning("Using `ubuntu` user")
            return "ubuntu"
    with suppress(KeyError):
        user = pwd.getpwuid(1000).pw_name
        _logger.warning("Using `%s` user", user)
        return user
    with suppress(KeyError):
        user = pwd.getpwuid(1001).pw_name
        _logger.warning("Using `%s` user", user)
        return user
    raise RuntimeError("Cannot guess which user should run unprivileged jobs!")
