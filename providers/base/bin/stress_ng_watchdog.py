#!/usr/bin/env python3
"""Store, disable and restore the systemd runtime watchdog.

An enabled systemd runtime (hardware) watchdog can reset the DUT while
stress-ng stressors starve the system (see PERI-991). The ``disable``
command records the current watchdog state and, only when the watchdog
is enabled, disables it with a systemd drop-in so no original
configuration file is modified. The ``restore`` command removes the
drop-in again and verifies the original value returned. Both commands
are no-ops when the watchdog was already disabled before the run.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

DROPIN_PATH = Path(
    "/etc/systemd/system.conf.d/99-checkbox-stress-ng-watchdog.conf"
)
DROPIN_CONTENT = "[Manager]\nRuntimeWatchdogSec=0\n"
STATE_FILE_NAME = "stress-ng-watchdog-original-usec"


def get_watchdog_usec() -> str:
    """Return the RuntimeWatchdogUSec value reported by systemd."""
    # stdout=PIPE + universal_newlines instead of capture_output/text:
    # this provider must stay Python 3.5 compatible (tox py35 env).
    result = subprocess.run(
        ["systemctl", "show", "-p", "RuntimeWatchdogUSec", "--value"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=True,
    )
    return result.stdout.strip()


def reload_systemd() -> None:
    """Re-execute the systemd manager so watchdog changes take effect."""
    subprocess.run(["systemctl", "daemon-reexec"], check=True)
    time.sleep(1)


def state_file() -> Path:
    """Return the session-share file holding the original watchdog value.

    Defaults to /tmp when PLAINBOX_SESSION_SHARE is not set, so the
    script can also be run on its own outside a Checkbox session.
    """
    session_share = os.environ.get("PLAINBOX_SESSION_SHARE", "/tmp")
    return Path(session_share) / STATE_FILE_NAME


def disable() -> int:
    """Record the watchdog state and disable the watchdog if enabled."""
    original = get_watchdog_usec()
    print("Original RuntimeWatchdogUSec: {}".format(original or "<unset>"))
    state_file().write_text(original)
    if original in ("", "0"):
        print("Runtime watchdog is already disabled. Keeping it disabled.")
        return 0
    print("Disabling runtime watchdog via systemd drop-in...")
    DROPIN_PATH.parent.mkdir(parents=True, exist_ok=True)
    DROPIN_PATH.write_text(DROPIN_CONTENT)
    reload_systemd()
    current = get_watchdog_usec()
    if current != "0":
        print("RuntimeWatchdogUSec is '{}', expected '0'".format(current))
        return 1
    print("Runtime watchdog disabled (original setting: {})".format(original))
    return 0


def restore() -> int:
    """Restore the watchdog to the state recorded by disable()."""
    if not state_file().exists():
        print("No stored watchdog state found; disable did not record it.")
        return 1
    original = state_file().read_text().strip()
    print("Original RuntimeWatchdogUSec: {}".format(original or "<unset>"))
    if not DROPIN_PATH.exists():
        print(
            "Watchdog was already disabled before the run. "
            "Nothing to restore."
        )
        return 0
    print("Removing drop-in and restoring original configuration...")
    DROPIN_PATH.unlink()
    reload_systemd()
    current = get_watchdog_usec()
    print("RuntimeWatchdogUSec after restore: {}".format(current or "<unset>"))
    if current != original:
        print(
            "Restored value '{}' does not match original '{}'".format(
                current, original
            )
        )
        return 1
    print("Runtime watchdog restored to its original state")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=["disable", "restore"],
        help="disable: record state and disable the watchdog if enabled; "
        "restore: undo what disable did and verify the original value",
    )
    args = parser.parse_args()
    if args.action == "disable":
        return disable()
    return restore()


if __name__ == "__main__":
    sys.exit(main())
