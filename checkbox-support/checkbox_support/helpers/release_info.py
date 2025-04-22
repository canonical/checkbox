import re
from contextlib import suppress


def get_release_file_content():
    with suppress(FileNotFoundError):
        with open("/var/lib/snapd/hostfs/etc/os-release", "r") as fp:
            return fp.read()
    with open("/etc/os-release", "r") as fp:
        return fp.read()


def get_release_info():

    release_file_content = get_release_file_content()

    os_release_map = {
        "NAME": "distributor_id",
        "PRETTY_NAME": "description",
        "VERSION_ID": "release",
        "VERSION_CODENAME": "codename",
    }
    os_release = {}
    lines = filter(bool, release_file_content.strip().splitlines())
    for line in lines:
        (key, value) = line.split("=", 1)
        if key in os_release_map:
            k = os_release_map[key]
            # Strip out quotes and newlines
            os_release[k] = re.sub('["\n]', "", value)
    # this is needed by C3, on core there is no VERSION_CODENAME, lets put
    # description (PRETTY_NAME) here by default or unknown (which should be
    # impossible but resources aren't supposed to crash)
    os_release["codename"] = os_release.get(
        "codename", os_release.get("description", "unknown")
    )
    return os_release
