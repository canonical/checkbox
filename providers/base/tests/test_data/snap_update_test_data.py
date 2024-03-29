from pathlib import Path

snapd_list_sample = [
    {
        "channel": "22/stable",
        "confinement": "strict",
        "contact": "",
        "description": (
            "The Ubuntu linux-raspi kernel package as a snap.\n"
            "\n"
            "This snap supports the Pi 2, 3 and 4. It is provided for "
            "both armhf and arm64 architectures."
        ),
        "developer": "canonical",
        "devmode": False,
        "id": "jeIuP6tfFrvAdic8DMWqHmoaoukAPNbJ",
        "ignore-validation": False,
        "install-date": "2023-09-04T17:45:02.067900703Z",
        "installed-size": 98791424,
        "jailmode": False,
        "links": None,
        "mounted-from": "/var/lib/snapd/snaps/pi-kernel_663.snap",
        "name": "pi-kernel",
        "private": False,
        "publisher": {
            "display-name": "Canonical",
            "id": "canonical",
            "username": "canonical",
            "validation": "verified",
        },
        "revision": "663",
        "status": "active",
        "summary": "The Ubuntu Raspberry Pi kernel",
        "title": "pi-kernel",
        "tracking-channel": "22/stable",
        "type": "kernel",
        "version": "5.15.0-1036.39",
    },
    {
        "channel": "latest/stable",
        "confinement": "strict",
        "contact": "https://github.com/snapcore/snapd/issues",
        "description": (
            "Install, configure, refresh and remove snap packages. Snaps "
            "are\n"
            "'universal' packages that work across many different Linux "
            "systems,\n"
            "enabling secure distribution of the latest apps and "
            "utilities for\n"
            "cloud, servers, desktops and the internet of things.\n"
            "\n"
            "Start with 'snap list' to see installed snaps."
        ),
        "developer": "canonical",
        "devmode": False,
        "icon": "https://dashboard.snapcraft.io/site_media/appmedia/2019/09/snapd.png",
        "id": "PMrrV4ml8uWuEUDBT8dSGnKUYbevVhc4",
        "ignore-validation": False,
        "install-date": "2023-09-06T18:37:40.283181077Z",
        "installed-size": 37236736,
        "jailmode": False,
        "license": "GPL-3.0",
        "links": {
            "contact": ["https://github.com/snapcore/snapd/issues"],
            "website": ["https://snapcraft.io"],
        },
        "media": [
            {
                "height": 460,
                "type": "icon",
                "url": "https://dashboard.snapcraft.io/site_media/appmedia/2019/09/snapd.png",
                "width": 460,
            },
            {
                "height": 648,
                "type": "screenshot",
                "url": "https://dashboard.snapcraft.io/site_media/appmedia/2019/09/Screenshot_20190924_115756_hLcyetO.png",
                "width": 956,
            },
            {
                "height": 648,
                "type": "screenshot",
                "url": "https://dashboard.snapcraft.io/site_media/appmedia/2019/09/Screenshot_20190924_115824_2v3y6l8.png",
                "width": 956,
            },
            {
                "height": 834,
                "type": "screenshot",
                "url": "https://dashboard.snapcraft.io/site_media/appmedia/2019/09/Screenshot_20190924_115055_Uuq7KIb.png",
                "width": 1023,
            },
            {
                "height": 648,
                "type": "screenshot",
                "url": "https://dashboard.snapcraft.io/site_media/appmedia/2019/09/Screenshot_20190924_125944.png",
                "width": 956,
            },
        ],
        "mounted-from": "/var/lib/snapd/snaps/snapd_20102.snap",
        "name": "snapd",
        "private": False,
        "publisher": {
            "display-name": "Canonical",
            "id": "canonical",
            "username": "canonical",
            "validation": "verified",
        },
        "revision": "20102",
        "status": "active",
        "summary": "Daemon and tooling that enable snap packages",
        "title": "snapd",
        "tracking-channel": "latest/stable",
        "type": "snapd",
        "version": "2.60.3",
        "website": "https://snapcraft.io",
    },
    {
        "apps": [
            {"name": "checkbox-cli", "snap": "checkbox"},
            {"name": "client-cert-iot-ubuntucore", "snap": "checkbox"},
            {"name": "configure", "snap": "checkbox"},
            {"name": "odm-certification", "snap": "checkbox"},
            {
                "active": True,
                "daemon": "simple",
                "daemon-scope": "system",
                "enabled": True,
                "name": "service",
                "snap": "checkbox",
            },
            {"name": "shell", "snap": "checkbox"},
            {"name": "sru", "snap": "checkbox"},
            {"name": "test-runner", "snap": "checkbox"},
        ],
        "base": "core22",
        "channel": "uc22/beta",
        "confinement": "strict",
        "contact": "",
        "description": (
            "Checkbox is a flexible test automation software.\n"
            "It’s the main tool used in Ubuntu Certification program.\n"
        ),
        "developer": "ce-certification-qa",
        "devmode": True,
        "id": "06zlGRiJvdhJMO5NFVNjIOcZ1g3m8yVb",
        "ignore-validation": False,
        "install-date": "2023-09-04T09:02:32.253731099Z",
        "installed-size": 12288,
        "jailmode": False,
        "links": None,
        "mounted-from": "/var/lib/snapd/snaps/checkbox_2784.snap",
        "name": "checkbox",
        "private": False,
        "publisher": {
            "display-name": "Canonical Certification Team",
            "id": "Euf8YO6waprpTXVrREuDw8ODHNIACTwi",
            "username": "ce-certification-qa",
            "validation": "unproven",
        },
        "revision": "2784",
        "status": "active",
        "summary": "Checkbox test runner",
        "title": "checkbox",
        "tracking-channel": "uc22/beta",
        "type": "app",
        "version": "2.9.1",
    },
    {
        "base": "core22",
        "channel": "latest/edge",
        "confinement": "strict",
        "contact": "",
        "description": "Checkbox runtime and public providers",
        "developer": "ce-certification-qa",
        "devmode": False,
        "id": "jUzbHhPAz1sQPzVD24Nky8UTbuKZ0gpR",
        "ignore-validation": False,
        "install-date": "2023-09-07T01:08:22.885438702Z",
        "installed-size": 168214528,
        "jailmode": False,
        "links": None,
        "mounted-from": "/var/lib/snapd/snaps/checkbox22_518.snap",
        "name": "checkbox22",
        "private": False,
        "publisher": {
            "display-name": "Canonical Certification Team",
            "id": "Euf8YO6waprpTXVrREuDw8ODHNIACTwi",
            "username": "ce-certification-qa",
            "validation": "unproven",
        },
        "revision": "518",
        "status": "active",
        "summary": "Checkbox runtime and public providers",
        "title": "checkbox22",
        "tracking-channel": "latest/edge",
        "type": "app",
        "version": "2.9.2.dev18+gd294291ef",
    },
    {
        "channel": "latest/stable",
        "confinement": "strict",
        "contact": "https://github.com/snapcore/core-base/issues",
        "description": "The base snap based on the Ubuntu 22.04 release.",
        "developer": "canonical",
        "devmode": False,
        "id": "amcUKQILKXHHTlmSa7NMdnXSx02dNeeT",
        "ignore-validation": False,
        "install-date": "2023-08-31T06:06:59.522300877Z",
        "installed-size": 71860224,
        "jailmode": False,
        "links": {"contact": ["https://github.com/snapcore/core-base/issues"]},
        "mounted-from": "/var/lib/snapd/snaps/core22_867.snap",
        "name": "core22",
        "private": False,
        "publisher": {
            "display-name": "Canonical",
            "id": "canonical",
            "username": "canonical",
            "validation": "verified",
        },
        "revision": "867",
        "status": "active",
        "summary": "Runtime environment based on Ubuntu 22.04",
        "title": "core22",
        "tracking-channel": "latest/stable",
        "type": "base",
        "version": "20230801",
    },
    {
        "base": "core22",
        "channel": "",
        "confinement": "strict",
        "contact": "",
        "description": (
            "Support files for booting Raspberry Pi.\n"
            "This gadget snap supports the Raspberry Pi 2B, 3B, 3A+, 3B+, "
            "4B, Compute\n"
            "Module 3, and the Compute Module 3+ universally.\n"
        ),
        "developer": "canonical",
        "devmode": False,
        "icon": "/v2/icons/pi/icon",
        "id": "YbGa9O3dAXl88YLI6Y1bGG74pwBxZyKg",
        "ignore-validation": False,
        "install-date": "2023-08-31T06:05:21.054039971Z",
        "installed-size": 11612160,
        "jailmode": False,
        "links": None,
        "mounted-from": "/var/lib/snapd/snaps/pi_132.snap",
        "name": "pi",
        "private": False,
        "publisher": {
            "display-name": "Canonical",
            "id": "canonical",
            "username": "canonical",
            "validation": "verified",
        },
        "revision": "132",
        "status": "active",
        "summary": "Raspberry Pi gadget",
        "tracking-channel": "22/stable",
        "type": "gadget",
        "version": "22-2",
    },
]

snapd_list_no_kernel_snapd_gadget_snap = [
    {
        "channel": "latest/stable",
        "confinement": "strict",
        "contact": "https://github.com/snapcore/core-base/issues",
        "description": "The base snap based on the Ubuntu 22.04 release.",
        "developer": "canonical",
        "devmode": False,
        "id": "amcUKQILKXHHTlmSa7NMdnXSx02dNeeT",
        "ignore-validation": False,
        "install-date": "2023-08-30T08:38:36.555233022Z",
        "installed-size": 77492224,
        "jailmode": False,
        "links": {"contact": ["https://github.com/snapcore/core-base/issues"]},
        "mounted-from": "/var/lib/snapd/snaps/core22_864.snap",
        "name": "core22",
        "private": False,
        "publisher": {
            "display-name": "Canonical",
            "id": "canonical",
            "username": "canonical",
            "validation": "verified",
        },
        "revision": "864",
        "status": "active",
        "summary": "Runtime environment based on Ubuntu 22.04",
        "title": "core22",
        "tracking-channel": "latest/stable",
        "type": "base",
        "version": "20230801",
    },
]

snapd_seed_glob_data = [
    Path("/var/lib/snapd/seed/snaps/firefox_2605.snap"),
    Path("/var/lib/snapd/seed/snaps/snapd_19267.snap"),
    Path("/var/lib/snapd/seed/snaps/pc-kernel_1289.snap"),
    Path("/var/lib/snapd/seed/snaps/core22_617.snap"),
]

snapd_list_firefox_snap = {
    "apps": [
        {
            "desktop-file": "/var/lib/snapd/desktop/applications/firefox_firefox.desktop",
            "name": "firefox",
            "snap": "firefox",
        },
        {"name": "geckodriver", "snap": "firefox"},
    ],
    "base": "core20",
    "channel": "latest/stable",
    "confinement": "strict",
    "contact": "https://support.mozilla.org/kb/file-bug-report-or-feature-request-mozilla",
    "description": "Firefox is a powerful, extensible web browser with support "
    "for modern web application technologies.",
    "developer": "mozilla",
    "devmode": False,
    "icon": "https://dashboard.snapcraft.io/site_media/appmedia/2021/12/firefox_logo.png",
    "id": "3wdHCAVyZEmYsCMFDE9qt92UV8rC8Wdk",
    "ignore-validation": False,
    "install-date": "2023-08-25T08:35:06.453124352+08:00",
    "installed-size": 248733696,
    "jailmode": False,
    "links": {
        "contact": [
            "https://support.mozilla.org/kb/file-bug-report-or-feature-request-mozilla"
        ],
        "website": ["https://www.mozilla.org/firefox/"],
    },
    "media": [
        {
            "height": 196,
            "type": "icon",
            "url": "https://dashboard.snapcraft.io/site_media/appmedia/2021/12/firefox_logo.png",
            "width": 196,
        },
        {
            "height": 1415,
            "type": "screenshot",
            "url": "https://dashboard.snapcraft.io/site_media/appmedia/2021/09/Screenshot_from_2021-09-30_08-01-50.png",
            "width": 1850,
        },
    ],
    "mounted-from": "/var/lib/snapd/snaps/firefox_3026.snap",
    "name": "firefox",
    "private": False,
    "publisher": {
        "display-name": "Mozilla",
        "id": "OgeoZuqQpVvSr9eGKJzNCrFGSaKXpkey",
        "username": "mozilla",
        "validation": "verified",
    },
    "revision": "3026",
    "status": "active",
    "summary": "Mozilla Firefox web browser",
    "title": "firefox",
    "tracking-channel": "latest/stable",
    "type": "app",
    "version": "116.0.3-2",
    "website": "https://www.mozilla.org/firefox/",
}

snapd_find_firefox_snap = [
    {
        "base": "core22",
        "categories": [{"featured": True, "name": "productivity"}],
        "channel": "stable",
        "channels": {
            "esr/candidate": {
                "channel": "esr/candidate",
                "confinement": "strict",
                "epoch": {"read": [0], "write": [0]},
                "released-at": "2023-08-21T18:15:17.435529Z",
                "revision": "3052",
                "size": 253628416,
                "version": "115.2.0esr-1",
            },
            "esr/stable": {
                "channel": "esr/stable",
                "confinement": "strict",
                "epoch": {"read": [0], "write": [0]},
                "released-at": "2023-08-29T12:37:31.563045Z",
                "revision": "3052",
                "size": 253628416,
                "version": "115.2.0esr-1",
            },
            "latest/beta": {
                "channel": "latest/beta",
                "confinement": "strict",
                "epoch": {"read": [0], "write": [0]},
                "released-at": "2023-09-04T01:41:28.490375Z",
                "revision": "3099",
                "size": 251957248,
                "version": "118.0b4-1",
            },
            "latest/candidate": {
                "channel": "latest/candidate",
                "confinement": "strict",
                "epoch": {"read": [0], "write": [0]},
                "released-at": "2023-08-24T23:00:15.702917Z",
                "revision": "3068",
                "size": 248352768,
                "version": "117.0-2",
            },
            "latest/edge": {
                "channel": "latest/edge",
                "confinement": "strict",
                "epoch": {"read": [0], "write": [0]},
                "released-at": "2023-09-04T03:53:25.23937Z",
                "revision": "3102",
                "size": 269561856,
                "version": "119.0a1",
            },
            "latest/stable": {
                "channel": "latest/stable",
                "confinement": "strict",
                "epoch": {"read": [0], "write": [0]},
                "released-at": "2023-08-29T12:37:04.958128Z",
                "revision": "3068",
                "size": 248352768,
                "version": "117.0-2",
            },
        },
        "confinement": "strict",
        "contact": "https://support.mozilla.org/kb/file-bug-report-or-feature-request-mozilla",
        "description": "Firefox is a powerful, extensible web browser with support "
        "for modern web application technologies.",
        "developer": "mozilla",
        "devmode": False,
        "download-size": 248352768,
        "icon": "https://dashboard.snapcraft.io/site_media/appmedia/2021/12/firefox_logo.png",
        "id": "3wdHCAVyZEmYsCMFDE9qt92UV8rC8Wdk",
        "ignore-validation": False,
        "jailmode": False,
        "license": "MPL-2.0",
        "links": {
            "contact": [
                "https://support.mozilla.org/kb/file-bug-report-or-feature-request-mozilla"
            ],
            "website": ["https://www.mozilla.org/firefox/"],
        },
        "media": [
            {
                "height": 196,
                "type": "icon",
                "url": "https://dashboard.snapcraft.io/site_media/appmedia/2021/12/firefox_logo.png",
                "width": 196,
            },
            {
                "height": 1415,
                "type": "screenshot",
                "url": "https://dashboard.snapcraft.io/site_media/appmedia/2021/09/Screenshot_from_2021-09-30_08-01-50.png",
                "width": 1850,
            },
        ],
        "name": "firefox",
        "private": False,
        "publisher": {
            "display-name": "Mozilla",
            "id": "OgeoZuqQpVvSr9eGKJzNCrFGSaKXpkey",
            "username": "mozilla",
            "validation": "verified",
        },
        "revision": "3068",
        "status": "available",
        "store-url": "https://snapcraft.io/firefox",
        "summary": "Mozilla Firefox web browser",
        "title": "firefox",
        "tracks": ["latest", "esr"],
        "type": "app",
        "version": "117.0-2",
        "website": "https://www.mozilla.org/firefox/",
    }
]

snap_info_pi_kernel = {
    "installed_revision": "567",
    "base_revision": "567",
    "name": "pi-kernel",
    "type": "kernel",
    "revisions": {
        "18-cm3/beta": "649",
        "18-cm3/edge": "649",
        "18-pi/beta": "667",
        "18-pi/candidate": "667",
        "18-pi/edge": "667",
        "18-pi/stable": "662",
        "18-pi2/beta": "649",
        "18-pi2/edge": "649",
        "18-pi3/beta": "649",
        "18-pi3/candidate": "649",
        "18-pi3/edge": "649",
        "18-pi3/stable": "649",
        "18-pi4/beta": "77",
        "18-pi4/candidate": "77",
        "18-pi4/edge": "77",
        "20/beta": "666",
        "20/candidate": "661",
        "20/edge": "666",
        "20/stable": "661",
        "22/beta": "663",
        "22/candidate": "663",
        "22/edge": "663",
        "22/stable": "658",
        "latest/candidate": "542",
    },
    "tracking_channel": "22/stable",
    "tracking_prefix": "22/",
}
