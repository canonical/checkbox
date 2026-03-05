#!/usr/bin/env python3
"""
Flow A (nomodeset):
  - Validate fbdev / firmware framebuffer path
    (/dev/fb0, efifb/simplefb/vesafb)
  - Optionally collect DRM render-only info as INFO (not required for display)

Flow B (normal):
  - Device registered -> driver bound -> DRM sysfs -> /dev/dri
    -> connectors/EDID/modes
  - Logs for link training / vblank/pageflip / power
  - Optional tools in --deep (modetest/kmsprint/drm_info)
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

DEBUGFS = Path("/sys/kernel/debug")
DRI_DEBUGFS = DEBUGFS / "dri"
TRACEFS = Path("/sys/kernel/tracing")

# ------------------------- helpers -------------------------


def run(cmd: List[str], timeout: int = 10) -> Tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=timeout,
            check=False,
        )
        return p.returncode, p.stdout.strip()
    except Exception as e:
        return 127, "<failed to run {}: {}>".format(cmd, e)


def read_text(path: Path, max_bytes: int = 200000) -> Optional[str]:
    try:
        data = path.read_bytes()
        if len(data) > max_bytes:
            data = data[:max_bytes] + b"\n<...truncated...>\n"
        return data.decode(errors="replace").strip()
    except Exception:
        return None


def which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def bullet(k: str, v: str) -> str:
    return "- {}: {}".format(k, v)


def is_root() -> bool:
    return os.geteuid() == 0


def grep_lines(
    text: str, patterns: List[str], max_hits: int = 80
) -> List[str]:
    hits = []  # type: List[str]
    for line in text.splitlines():
        for pat in patterns:
            if re.search(pat, line, re.IGNORECASE):
                hits.append(line)
                break
        if len(hits) >= max_hits:
            hits.append("<...more matches truncated...>")
            break
    return hits


def parse_cmdline() -> Dict[str, str]:
    cmdline = read_text(Path("/proc/cmdline")) or ""
    tokens = cmdline.split()
    out = {}  # type: Dict[str, str]
    for t in tokens:
        if "=" in t:
            k, v = t.split("=", 1)
            out[k] = v
        else:
            out[t] = "1"
    out["_raw"] = cmdline
    return out


def ensure_debugfs_ready() -> Tuple[bool, str]:
    if not DEBUGFS.is_dir():
        return False, "{} not present".format(DEBUGFS)
    if not DRI_DEBUGFS.is_dir():
        return (
            False,
            "{} not present (is debugfs mounted? "
            "try: sudo mount -t debugfs none /sys/kernel/debug)".format(
                DRI_DEBUGFS
            ),
        )
    return True, "ok"


def list_dri_debug_cards() -> List[int]:
    try:
        if not DRI_DEBUGFS.is_dir():
            return []
        out = []
        for p in DRI_DEBUGFS.iterdir():
            active = 0
            if p.is_dir() and p.name.isdigit():
                try:
                    with open("{}/state".format(p)) as f:
                        active = "active=1" in f.read()
                except FileNotFoundError:
                    pass

                if active:
                    out.append(int(p.name))
        return sorted(out)
    except PermissionError:
        print("permission denied (run as root):")
        return None


def pick_primary_card() -> Optional[int]:
    # Simple heuristic: pick lowest card index in debugfs.
    cards = list_dri_debug_cards()
    return cards[0] if cards else None


# ----------------------- check vblank event -----------------------


def _write(path: Path, data: str) -> None:
    path.write_text(data, encoding="utf-8")


def _exists_enable_file(ev: str) -> Optional[Path]:
    # "drm:drm_vblank_event" ->
    # /sys/kernel/tracing/events/drm/drm_vblank_event/enable
    if ":" not in ev:
        return None
    cat, name = ev.split(":", 1)
    p = TRACEFS / "events" / cat / name / "enable"
    return p if p.exists() else None


def disable_all_drm_events() -> int:
    """
    Equivalent to:
      for p in events/drm/*/enable; do echo 0 > "$p" 2>/dev/null || true; done

    Returns how many enable files we attempted to disable.
    """
    base = TRACEFS / "events" / "drm"
    if not base.is_dir():
        return 0
    count = 0
    for enable_file in base.glob("*/enable"):
        try:
            _write(enable_file, "0")
        except Exception:
            # ignore permission / missing etc, like the bash '|| true'
            pass
        count += 1
    return count


def count_trace_lines() -> int:
    """
    Equivalent to: grep -c "" trace
    Counts lines in /sys/kernel/tracing/trace
    """
    trace_path = TRACEFS / "trace"
    try:
        # read in one shot; trace is usually manageable after a short capture
        txt = trace_path.read_text(errors="replace")
        # count lines; splitlines counts correctly even without final newline
        return len(txt.splitlines())
    except Exception:
        return -1


def capture_drm_trace(
    duration_s: int = 10,
    events: Optional[List[str]] = None,
    cleanup_disable_all: bool = True,
) -> int:
    """
    Python version of tracefs script + count lines + disable all drm events.
    Requires root (or tracefs write permission).
    Returns line count, or 0 on error.
    """
    try:
        if not TRACEFS.is_dir():
            return 0

        if events is None:
            events = [
                "drm:drm_atomic_commit",
                "drm:drm_vblank_event",
                "drm:drm_vblank_event_delivered",
            ]

        # Stop tracing + clear buffer
        _write(TRACEFS / "tracing_on", "0")
        _write(TRACEFS / "trace", "")

        enabled = []  # type: List[str]
        for ev in events:
            enable_file = _exists_enable_file(ev)
            if enable_file:
                _write(enable_file, "1")
                enabled.append(ev)

        # Capture
        _write(TRACEFS / "tracing_on", "1")
        time.sleep(duration_s)
        _write(TRACEFS / "tracing_on", "0")

        # Count lines (events)
        line_count = count_trace_lines()

        # Cleanup: disable all drm events
        if cleanup_disable_all:
            disable_all_drm_events()

        return line_count

    except PermissionError:
        print("permission denied (run as root)")
        return 0


# ----------------------- check framebuffer flip -----------------------

_FB_RE = re.compile(r"\bfb=([0-9]+)\b")


def _extract_fb_ids_from_state(state_text: str) -> List[int]:
    # Very generic: collect all "fb=<id>" occurrences.
    return [int(m.group(1)) for m in _FB_RE.finditer(state_text)]


def check_framebuffer_flips(
    card: int, samples: int = 10, interval_s: float = 0.2
) -> int:
    """
    Return flips_seen = number of times fb IDs changed between samples.

    Runs flash_screen.py in the background to generate framebuffer activity.
    """
    state_path = DRI_DEBUGFS / str(card) / "state"
    txt0 = read_text(state_path)
    if txt0 is None:
        return 0

    # Start flash_screen.py to generate framebuffer flips
    flash_screen_path = Path(__file__).parent / "flash_screen.py"
    flash_proc = None
    if flash_screen_path.exists():
        try:
            flash_proc = subprocess.Popen(
                [sys.executable, str(flash_screen_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            print("[WARN] Failed to start flash_screen.py: {}".format(e))

    try:
        prev = sorted(set(_extract_fb_ids_from_state(txt0)))
        flips = 0
        for _ in range(samples - 1):
            time.sleep(interval_s)
            txt = read_text(state_path)
            if txt is None:
                break
            cur = sorted(set(_extract_fb_ids_from_state(txt)))
            if cur != prev:
                flips += 1
                prev = cur
        return flips
    finally:
        # Terminate flash_screen.py if it's still running
        if flash_proc is not None:
            flash_proc.terminate()
            try:
                flash_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                flash_proc.kill()


# --------------------------check PHY power state and Panel power state-


PsrAlpmResult = NamedTuple(
    "PsrAlpmResult",
    [
        ("supported", bool),
        ("psr_enabled", Optional[bool]),
        ("psr_active", Optional[bool]),
        ("alpm_active_hint", Optional[bool]),
        ("raw_excerpt", str),
        ("details", str),
    ],
)


def _bool_from_line(line: str) -> Optional[bool]:
    # Common formats: "Enabled: yes/no", "PSR enabled: 1/0", "Active: yes/no"
    low = line.strip().lower()
    if any(x in low for x in ("yes", "enabled", ": 1", "=1")) and not any(
        x in low for x in ("no", ": 0", "=0", "disabled")
    ):
        return True
    if any(x in low for x in ("no", "disabled", ": 0", "=0")):
        return False
    return None


def check_psr_alpm_state(card: int) -> PsrAlpmResult:
    """
    Best-effort, vendor-specific:
    - Strong support for Intel i915 via i915_edp_psr_status
    - For other drivers, likely unsupported unless you extend it
    """
    base = DRI_DEBUGFS / str(card)
    psr_path = base / "i915_edp_psr_status"
    txt = read_text(psr_path)
    if txt is None:
        return PsrAlpmResult(
            False,
            None,
            None,
            None,
            "",
            "Missing/unreadable: {} (i915-only)".format(psr_path),
        )

    psr_enabled = None
    psr_active = None
    alpm_hint = None

    excerpt_lines = []  # type: List[str]
    for line in txt.splitlines():
        low = line.lower()

        # PSR signals (formats differ slightly by kernel)
        if "psr" in low and ("enabled" in low or "enable" in low):
            b = _bool_from_line(line)
            if b is not None and psr_enabled is None:
                psr_enabled = b
        if "psr" in low and ("active" in low or "state" in low):
            # "Active: yes" / "PSR status: active"
            if "active" in low and ("yes" in low or "active" in low):
                psr_active = True
            if "inactive" in low or "not active" in low:
                psr_active = False

        # ALPM hints (often appears as "ALPM" string)
        if "alpm" in low:
            # If file explicitly says active/enabled, capture it
            if "enable" in low or "active" in low or "on" in low:
                alpm_hint = True
            if "disable" in low or "off" in low:
                alpm_hint = False

        # Keep a useful excerpt for reporting
        if any(
            k in low for k in ("psr", "alpm", "sink", "source", "dc3", "link")
        ):
            excerpt_lines.append(line)

    excerpt = "\n".join(excerpt_lines[:60])
    print(
        "[INFO] PSR/ALPM details: ",
        PsrAlpmResult(
            True,
            psr_enabled,
            psr_active,
            alpm_hint,
            excerpt,
            "parsed from {}".format(psr_path),
        ),
    )
    return not psr_active and not alpm_hint


# ------------------------- shared DRM helpers -------------------------


def list_sys_class_drm() -> List[Path]:
    base = Path("/sys/class/drm")
    if not base.is_dir():
        return []
    return sorted([p for p in base.iterdir() if p.is_dir()])


def drm_cards() -> List[Path]:
    return [
        p for p in list_sys_class_drm() if re.fullmatch(r"card\d+", p.name)
    ]


def get_driver_for_card(card: Path) -> Optional[str]:
    d = card / "device" / "driver"
    try:
        if d.is_symlink():
            return Path(os.readlink(str(d))).name
    except Exception:
        pass
    return None


def device_identity(card: Path) -> Dict[str, str]:
    out = {}  # type: Dict[str, str]
    dev = card / "device"
    for k in [
        "vendor",
        "device",
        "subsystem_vendor",
        "subsystem_device",
        "class",
    ]:
        t = read_text(dev / k)
        if t:
            out[k] = t
    ue = read_text(dev / "uevent")
    if ue:
        for line in ue.splitlines():
            if line.startswith(("DRIVER=", "PCI_ID=", "MODALIAS=")):
                k, v = line.split("=", 1)
                out[k] = v
    return out


def list_dev_dri_nodes() -> List[str]:
    dri = Path("/dev/dri")
    if not dri.is_dir():
        return []
    return [p.name for p in sorted(dri.iterdir())]


def drm_connectors_for(card: Path) -> List[Path]:
    prefix = card.name + "-"
    out = []
    for p in list_sys_class_drm():
        if p.name.startswith(prefix) and (p / "status").exists():
            out.append(p)
    return out


def connector_info(conn: Path) -> Dict[str, str]:
    info = {"name": conn.name}  # type: Dict[str, str]
    for f in ["status", "enabled", "dpms", "modes", "link_status"]:
        t = read_text(conn / f)
        if t is not None:
            info[f] = t
    edid = conn / "edid"
    if edid.exists():
        try:
            info["edid_bytes"] = str(edid.stat().st_size)
        except Exception:
            info["edid_bytes"] = "?"
    return info


def module_param(mod: str, param: str) -> Optional[str]:
    p = Path("/sys/module") / mod / "parameters" / param
    return read_text(p)


def runtime_pm_info(card: Path) -> Dict[str, str]:
    out = {}  # type: Dict[str, str]
    p = card / "device" / "power"
    if not p.is_dir():
        return out
    for k in [
        "runtime_status",
        "runtime_suspended_time",
        "runtime_active_time",
        "control",
        "autosuspend_delay_ms",
    ]:
        t = read_text(p / k)
        if t is not None:
            out[k] = t
    return out


# ------------------------- Flow A: nomodeset / fbdev -------------------------


def run_flow_nomodeset():
    print("[INFO] Flow: nomodeset (fbdev / firmware framebuffer)")

    fb0 = Path("/dev/fb0")
    if fb0.exists():
        print("[PASS] /dev/fb0 exists (fbdev path available)")
    else:
        raise SystemExit(
            "[FAIL] /dev/fb0 missing (expected with nomodeset). "
            "Check efifb/simplefb/vesafb/simpledrm."
        )

    # sysfs fb info
    fb_sys = Path("/sys/class/graphics/fb0")
    if fb_sys.is_dir():
        for f in ["name", "modes", "virtual_size", "stride", "bits_per_pixel"]:
            t = read_text(fb_sys / f)
            if t is not None:
                print("[INFO] fb0 {}: {}".format(f, t))
        # driver symlink if present
        drv = fb_sys / "device" / "driver"
        if drv.exists():
            try:
                if drv.is_symlink():
                    drv_name = Path(os.readlink(str(drv))).name
                    print("[INFO] fb0 driver: {}".format(drv_name))
            except Exception:
                pass
    else:
        raise SystemExit(
            "[FAIL] /sys/class/graphics/fb0 not found; "
            "fbdev sysfs info missing"
        )

    return


# ------------------------- Flow B: normal DRM/KMS -------------------------


def run_flow_kms():
    print("[INFO] Flow: normal DRM/KMS")

    # 1) DRM registered (sysfs)
    sys_drm = list_sys_class_drm()
    if not sys_drm:
        raise SystemExit(
            "[FAIL] /sys/class/drm missing/empty: "
            "DRM not exporting state (driver not loaded/bound?)"
        )
    print(
        "[PASS] /sys/class/drm entries: " + ", ".join(p.name for p in sys_drm)
    )

    cards = drm_cards()
    if not cards:
        raise SystemExit(
            "[FAIL] No /sys/class/drm/cardN found: "
            "DRM device not registered (driver missing/not bound?)"
        )
    print("[PASS] Found DRM cards: " + ", ".join(c.name for c in cards))

    # 2) Driver bound
    any_driver = False
    for c in cards:
        drv = get_driver_for_card(c)
        ident = device_identity(c)
        if drv:
            any_driver = True
            print("[PASS] {}: driver bound = {}".format(c.name, drv))
        else:
            raise SystemExit(
                "[FAIL] {}: no driver bound symlink".format(c.name)
            )
        if ident:
            brief = ", ".join(
                "{}={}".format(k, v)
                for k, v in ident.items()
                if k in ("DRIVER", "PCI_ID", "vendor", "device", "class")
            )
            print(
                "[INFO] {}: identity: {}".format(c.name, brief or "<partial>")
            )

        pm = runtime_pm_info(c)
        if pm:
            print(
                "[INFO] "
                + "{} runtime PM: ".format(c.name)
                + ", ".join("{}={}".format(k, v) for k, v in pm.items())
            )

    if not any_driver:
        raise SystemExit(
            "[FAIL] DRM cards exist but none show a bound driver: "
            "probe/bind issue"
        )

    # 3) /dev/dri nodes
    dri_nodes = list_dev_dri_nodes()
    if not dri_nodes:
        raise SystemExit(
            "[FAIL] /dev/dri missing/empty: udev/devtmpfs nodes not created"
        )
    print("[INFO] /dev/dri nodes: " + ", ".join(dri_nodes))

    has_card = any(n.startswith("card") for n in dri_nodes)
    has_render = any(n.startswith("renderD") for n in dri_nodes)
    if not has_card:
        raise SystemExit(
            "[FAIL] No /dev/dri/card*: compositor cannot open KMS"
        )
    print("[PASS] /dev/dri/card* present (KMS node)")

    if has_render:
        print("[PASS] /dev/dri/renderD* present (render node)")
    else:
        raise SystemExit(
            "[FAIL] No /dev/dri/renderD*: "
            "Mesa may fall back to llvmpipe or rendering may fail"
        )

    # 4) KMS gating module params
    params = []
    for mod, param in [
        ("nvidia_drm", "modeset"),
        ("i915", "modeset"),
        ("amdgpu", "dc"),
        ("radeon", "modeset"),
    ]:
        v = module_param(mod, param)
        if v is not None:
            params.append("{}.{}={}".format(mod, param, v))
    print(
        "[INFO] modeset params: "
        + (", ".join(params) if params else "<none readable>")
    )
    if any(p.startswith("nvidia_drm.modeset=0") for p in params):
        raise SystemExit(
            "[FAIL] nvidia_drm.modeset=0: KMS disabled for NVIDIA DRM "
            "(often black screen on Wayland)"
        )

    # 5) Connection / EDID / modes
    any_connected = False
    for c in cards:
        conns = drm_connectors_for(c)
        if not conns:
            continue
        for conn in conns:
            ci = connector_info(conn)
            status = (ci.get("status") or "").strip()
            modes = (ci.get("modes") or "").splitlines()
            edid_bytes = ci.get("edid_bytes", "0")
            link_status = (ci.get("link_status") or "").strip()
            info_msg = (
                "[INFO] {}: status={}, "
                "edid_bytes={}, modes={}".format(
                    ci["name"], status or "<unknown>", edid_bytes, len(modes)
                )
            )
            if link_status:
                info_msg += ", link_status={}".format(link_status)
            print(info_msg)
            if status == "connected":
                any_connected = True
                if len(modes) == 0:
                    raise SystemExit(
                        "[FAIL] {}: connected but no modes "
                        "(EDID/AUX/DDC/link issue)".format(ci["name"])
                    )
                if edid_bytes in ("0", "", "?"):
                    print(
                        "[WARN] {}: EDID size suspicious "
                        "(edid_bytes={})".format(ci["name"], edid_bytes)
                    )
                if link_status and link_status.lower() != "good":
                    raise SystemExit(
                        "[FAIL] {}: link_status={}".format(
                            ci["name"], link_status
                        )
                    )

    if any_connected:
        print("[PASS] At least one connector is connected")
    else:
        raise SystemExit(
            "[FAIL] No connectors report connected "
            "(if you expect display: cable/hotplug/link training)"
        )

    # 6) runtime checkiong
    card = pick_primary_card()
    if card is None:
        raise SystemExit("[FAIL] no /sys/kernel/debug/dri/<N> found")
    else:
        vb = capture_drm_trace(duration_s=10)
        if vb:
            print("[PASS] check vblank_event count: {}".format(vb))
        else:
            raise SystemExit("[FAIL] no vblank found")

        flips = check_framebuffer_flips(card, samples=10, interval_s=2)
        if flips:
            print("[PASS] check framebuffer flips count: {}".format(flips))
        else:
            raise SystemExit("[FAIL] framebuffer has no flips")

        psr_alpm = check_psr_alpm_state(card)
        if psr_alpm:
            print("[PASS] PSR/ALPM status is ok")
        else:
            raise SystemExit("[FAIL] PSR/ALPM status is abnormal")

    return


# ------------------------- main -------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--expect-kms",
        action="store_true",
        help="Treat missing KMS pieces as FAIL (desktop expectation).",
    )
    args = ap.parse_args()

    cmd = parse_cmdline()
    print("[INFO] " + bullet("Kernel cmdline", cmd.get("_raw", "")))

    nomodeset = ("nomodeset" in cmd) or (cmd.get("nomodeset") == "1")
    if nomodeset and args.expect_kms:
        print("The system run with nomodeset but we expected KMS.")
        return
        # logging.error("The system run with nomodeset but we expected KMS.")
        # raise SystemExit("FAIL: RPMSG channel is not created")
    elif nomodeset:
        run_flow_nomodeset()
    else:
        run_flow_kms()


if __name__ == "__main__":
    sys.exit(main())
