#! /usr/bin/python3

import re
import subprocess as sp
import typing as T


# Not going to try to parse these test names since the
# ioctls in the test are not necessarily described in its name
TEST_NAME_TO_IOCTL_MAP = {
    "VIDIOC_QUERYCAP": ["VIDIOC_QUERYCAP"],
    "VIDIOC_G/S_PRIORITY": ["VIDIOC_G_PRIORITY", "VIDIOC_S_PRIORITY"],
    "VIDIOC_DBG_G/S_REGISTER": [
        "VIDIOC_DBG_G_REGISTER",
        "VIDIOC_DBG_S_REGISTER",
    ],
    "VIDIOC_LOG_STATUS": ["VIDIOC_LOG_STATUS"],
    "VIDIOC_G/S_TUNER/ENUM_FREQ_BANDS": [
        "VIDIOC_G_TUNER",
        "VIDIOC_S_TUNER",
        "VIDIO_ENUM_FREQ_BANDS",
    ],
    "VIDIOC_S_HW_FREQ_SEEK": ["VIDIOC_S_HW_FREQ_SEEK"],
    "VIDIOC_ENUMAUDIO": ["VIDIOC_ENUMAUDIO"],
    "VIDIOC_G/S/ENUMINPUT": [
        "VIDIOC_G_SELECTION",
        "VIDIOC_ENUMINPUT",
        "VIDIOC_S_INPUT",
    ],
    "VIDIOC_G/S_AUDIO": ["VIDIOC_G_AUDIO", "VIDIOC_S_AUDIO"],
    "VIDIOC_G/S_MODULATOR": ["VIDIOC_G_MODULATOR", "VIDIOC_S_MODULATOR"],
    "VIDIOC_G/S_FREQUENCY": ["VIDIOC_G_FREQUENCY", "VIDIOC_S_FREQUENCY"],
    "VIDIOC_ENUMAUDOUT": ["VIDIOC_ENUMAUDOUT"],
    "VIDIOC_G/S/ENUMOUTPUT": [
        "VIDIOC_G_OUTPUT",
        "VIDIOC_S_OUTPUT",
        "VIDIOC_ENUMOUTPUT",
    ],
    "VIDIOC_G/S_AUDOUT": ["VIDIOC_G_AUDOUT", "VIDIOC_S_AUDOUT"],
    "VIDIOC_ENUM/G/S/QUERY_STD": [
        "VIDIOC_ENUMSTD",
        "VIDIOC_G_STD",
        "VIDIOC_S_STD",
        "VIDIOC_QUERYSTD",
    ],
    "VIDIOC_ENUM/G/S/QUERY_DV_TIMINGS": [
        "VIDIOC_G_DV_TIMINGS",
        "VIDIOC_ENUM_DV_TIMINGS",
        "VIDIOC_QUERY_DV_TIMINGS",
    ],
    "VIDIOC_DV_TIMINGS_CAP": ["VIDIOC_DV_TIMINGS_CAP"],
    "VIDIOC_G/S_EDID": ["VIDIOC_G_EDID", "VIDIOC_S_EDID"],
    "VIDIOC_QUERY_EXT_CTRL/QUERYMENU": [
        "VIDIOC_QUERYMENU",
        "VIDIOC_QUERY_EXT_CTRL",
    ],
    "VIDIOC_QUERYCTRL": ["VIDIOC_QUERYCTRL"],
    "VIDIOC_G/S_CTRL": ["VIDIOC_G_CTRL", "VIDIOC_S_CTRL"],
    "VIDIOC_G/S/TRY_EXT_CTRLS": [
        "VIDIOC_G_EXT_CTRLS",
        "VIDIOC_S_EXT_CTRLS",
        "VIDIOC_TRY_EXT_CTRLS",
    ],
    "VIDIOC_(UN)SUBSCRIBE_EVENT/DQEVENT": [
        "VIDIOC_SUBSCRIBE_EVENT",
        "VIDIOC_UNSUBSCRIBE_EVENT",
    ],
    "VIDIOC_G/S_JPEGCOMP": ["VIDIOC_G_JPEGCOMP", "VIDIOC_S_JPEGCOMP"],
    "VIDIOC_ENUM_FMT/FRAMESIZES/FRAMEINTERVALS": [
        "VIDIOC_ENUM_FMT",
        "VIDIOC_ENUM_FRAMEINTERVALS",
        "VIDIOC_ENUM_FRAMESIZES",
    ],
    "VIDIOC_G/S_PARM": ["VIDIOC_G_PARM", "VIDIOC_S_PARM"],
    "VIDIOC_G_FBUF": ["VIDIOC_G_FBUF"],
    "VIDIOC_G_FMT": ["VIDIOC_G_FMT"],
    "VIDIOC_TRY_FMT": ["VIDIOC_TRY_FMT"],
    "VIDIOC_S_FMT": ["VIDIOC_S_FMT"],
    "VIDIOC_G_SLICED_VBI_CAP": ["VIDIOC_G_SLICED_VBI_CAP"],
    "VIDIOC_(TRY_)ENCODER_CMD": [
        "VIDIOC_ENCODER_CMD",
        "VIDIOC_TRY_ENCODER_CMD",
    ],
    "VIDIOC_G_ENC_INDEX": ["VIDIOC_G_ENC_INDEX"],
    "VIDIOC_(TRY_)DECODER_CMD": [
        "VIDIOC_DECODER_CMD",
        "VIDIOC_TRY_DECODER_CMD",
    ],
    "VIDIOC_REQBUFS/CREATE_BUFS/QUERYBUF": [
        "VIDIOC_REQBUFS",
        "VIDIOC_CREATE_BUFS",
        "VIDIOC_QUERYBUF",
    ],
    "VIDIOC_EXPBUF": ["VIDIOC_EXPBUF"],
}


# see the summary dict literal for actual keys
Summary = T.Dict[str, T.Union[int, str]]
# see the details dict literal for actual keys
Details = T.Dict[str, T.List[str]]


def get_test_name_from_line(line: str) -> T.Tuple[str, bool]:
    """Gets the test name and returns whether the line includes a ioctl name
    - Some tests could look like "test multiple open" -> doesn't include a name
    :param line: a single line from v4l2 compliance output
    :return: tuple of test_name, is_ioctl_name
    """
    assert line.startswith(
        "test"
    ), "This line doesn't describe a test output. Line is {}".format(line)
    test_name = line.split("test ", maxsplit=1)[1].split(": ", maxsplit=1)[0]
    return test_name, test_name.startswith("VIDIOC")


def parse_v4l2_compliance(
    device: T.Optional[str] = None,
) -> T.Tuple[Summary, Details]:
    """Parses the output of v4l2-compliance

    :param device: which device to test, defaults to "/dev/video0",
    it can also be an integer. See v4l2-compliance -h
    :type device: T.Union[int, str], optional
    :return: 2 dictionaries (summary, details).
    NOTE: summary comes from directly parsing the numbers in the last line of
    v4l2-compliance and it does **NOT** match the array sizes in Details
    since we map the test names to actual ioctls.

    :rtype: T.Tuple[Summary, Details]
    """

    out = sp.run(
        [
            "v4l2-compliance",
            *(["-d", str(device)] if device else []),
            "-C",
            "never", # dont show colors
        ],
        universal_newlines=True,
        stdout=sp.PIPE,
        stderr=sp.PIPE,
    )  # can't really depend on the return code here
    # since any failure => return code 1

    error_prefixes = ("Failed to open", "Cannot open device")
    if any(out.stderr.startswith(prefix) for prefix in error_prefixes):
        # can't open the device
        raise FileNotFoundError(out.stderr)

    lines = []  # type: list[str]
    for line in out.stdout.splitlines():
        clean_line = line.strip()
        if clean_line != "":
            lines.append(clean_line)

    pattern = (
        r"Total for (.*): (.*), Succeeded: (.*), Failed: (.*), Warnings: (.*)"
    )
    match_output = re.match(pattern, lines[-1])

    assert match_output is not None, (
        "There's no summary line in v4l2-compliance's output. "
        "Output might be corrupted. Last line is: \n {}".format(lines[-1])
    )

    summary = {
        "device_name": match_output.group(1),
        "total": int(match_output.group(2)),
        "succeeded": int(match_output.group(3)),
        "failed": int(match_output.group(4)),
        "warnings": int(match_output.group(5)),
    }

    details = {
        "succeeded": [],
        "failed": [],
        "not_supported": [],
    }  # type: dict[str, list[str]]

    for line in lines:
        if line.endswith(": OK"):
            result = "succeeded"
        elif line.endswith(": OK (Not Supported)"):
            result = "not_supported"
        elif line.endswith(": FAIL"):
            result = "failed"
        else:
            continue

        name, is_ioctl_name = get_test_name_from_line(line)
        if is_ioctl_name:
            # ignore unknown test names, just don't append
            for ioctl_name in TEST_NAME_TO_IOCTL_MAP.get(name, []):
                details[result].append(ioctl_name)

    return summary, details
