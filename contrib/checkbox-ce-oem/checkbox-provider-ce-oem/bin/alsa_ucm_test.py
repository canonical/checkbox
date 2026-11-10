#!/usr/bin/env python3

# Copyright 2012-2026 Canonical Ltd.
# Written by:
#   Isaac Yang <isaac.yang@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
This script is a lightweight helper for Checkbox-style ALSA UCM validation.
It extracts card/verb/device discovery logic from the full
`alsa_ucm_inspector_router.py` and provides three subcommands:

- `resource`: emits card/verb/device rows for Checkbox resource jobs. It can
  output sink-only rows, source-only rows, or loopback pair rows. Optional
  `--pairing` applies in every mode: paired sinks/sources
  are omitted from sink/source lists, while `resource loopback` lists only
  those pairs; omitting the mode with `--pairing` merges loopback rows plus
  filtered sinks and sources.
- `test`: validates one card+verb+device row by applying UCM configuration
  via `alsaucm` and running a stream verification (speaker-test or arecord),
  with an optional `--dry-run` mode for safe QA validation.
- `loopback-test`: enables one Sink device and one Source device under the
  same verb, runs playback + capture concurrently, and saves a WAV file for
  inspection.

Checkbox calls `test` **once per resource row**, passing exactly one
card+verb+device per invocation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

DEFAULT_SAMPLE_FORMAT = "S16_LE"
DEFAULT_SAMPLE_RATE = 48000
DEFAULT_RECORD_DURATION = 10
MAX_TEST_CHANNELS = 2

TIMEOUT_ALSAUCM_APPLY = 15
TIMEOUT_ALSAUCM_QUERY = 10

WAV_MIN_SIZE_DIVISOR = 100

UCM_TYPE_SINK = "Sink"
UCM_TYPE_SOURCE = "Source"
UCM_TYPE_UNKNOWN = "Unknown"


@dataclass
class TestContext:
    """Card and verb resolved for one test run."""

    card_name: str
    card_index: int
    resolved_card: str
    card_label: str
    verb_map: dict[str, dict[str, object]]
    resolved_verb: str


def warn(message: str) -> None:
    """Print warning messages to stderr with a shared prefix."""
    print(f"[WARN] {message}", file=sys.stderr)


class CardManager:
    """Discover sound cards and basic UCM information."""

    def list_cards(self) -> list[dict[str, object]]:
        """Read the sound cards from /proc/asound/cards.

        Each card has a header line and a long-name line, for example::

             0 [mt8391evk      ]: mt8391-evk - mt8391-evk
                                  mediatek-Genio720520EVKP2V3eMMCBoot-...

        The regex matches only the header line and gives
        ``idx="0"`` and ``short="mt8391evk      "``.
        """
        proc_path = Path("/proc/asound/cards")
        if not proc_path.exists():
            return []
        line_pattern = re.compile(r"^\s*(?P<idx>\d+)\s+\[(?P<short>[^\]]+)\]:")
        cards = []
        for line in proc_path.read_text(errors="replace").splitlines():
            match = line_pattern.match(line)
            if match:
                cards.append(
                    {
                        "index": int(match.group("idx")),
                        "short_name": match.group("short").strip(),
                    }
                )
        return cards

    def get_card(self, card_selector: str) -> dict[str, object] | None:
        """Find card by index or short name."""
        cards = self.list_cards()
        for card in cards:
            if str(card["index"]) == str(card_selector):
                return card
            if card["short_name"].lower() == str(card_selector).lower():
                return card
        return None

    def list_alsaucm_verbs(self, card_index: int) -> list[dict[str, str]]:
        """Enumerate UCM verbs from alsaucm list output.

        ``alsaucm -c 0 list _verbs`` prints, for example::

              0: HiFi
                Play high quality music

        The regex matches ``  0: HiFi`` and gives ``HiFi``. The next
        indented lines are the verb comment.
        """
        res = subprocess.run(
            ["alsaucm", "-c", str(card_index), "list", "_verbs"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_ALSAUCM_QUERY,
        )
        if res.returncode != 0:
            warn(
                f"alsaucm list _verbs failed for card {card_index} "
                f"(rc={res.returncode})"
            )
            return []

        verbs = []
        current = None
        for raw_line in res.stdout.splitlines():
            line = raw_line.rstrip()
            match = re.match(r"^\s*\d+:\s+(.+?)\s*$", line)
            if match:
                if current:
                    verbs.append(current)
                current = {"name": match.group(1).strip(), "comment": ""}
                continue
            if current and line.strip():
                if current["comment"]:
                    current["comment"] += f" {line.strip()}"
                else:
                    current["comment"] = line.strip()
        if current:
            verbs.append(current)
        return verbs


class UCMJsonParser:
    """Read verb and device names from alsaucm dump json."""

    def _infer_device_io(
        self, values: dict[str, str]
    ) -> tuple[str, str | None, str]:
        """Infer device type, PCM path, and channel count from UCM values."""
        pb_pcm = (values or {}).get("PlaybackPCM", "")
        cap_pcm = (values or {}).get("CapturePCM", "")
        dtype = UCM_TYPE_UNKNOWN
        pcm = None
        channels = "2"
        if pb_pcm:
            dtype = UCM_TYPE_SINK
            pcm = pb_pcm
            channels = (values or {}).get("PlaybackChannels", channels)
        elif cap_pcm:
            dtype = UCM_TYPE_SOURCE
            pcm = cap_pcm
            channels = (values or {}).get("CaptureChannels", channels)
        return dtype, pcm, channels

    def _make_device(
        self,
        name: str,
        comment: str = "",
        values: dict[str, str] | None = None,
    ) -> dict[str, object]:
        """Build a device dict with inferred I/O metadata."""
        values = values or {}
        dtype, pcm, channels = self._infer_device_io(values)
        return {
            "name": name,
            "comment": comment or "",
            "values": values,
            "type": dtype,
            "pcm": pcm,
            "channels": channels,
        }

    def run_alsaucm_dump(self, card_index: int) -> dict[str, object]:
        """Run alsaucm dump json and return parsed object."""
        res = subprocess.run(
            ["alsaucm", "-c", str(card_index), "dump", "json"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_ALSAUCM_QUERY,
        )
        if res.returncode != 0:
            warn(
                f"alsaucm dump json failed for card {card_index} "
                f"(rc={res.returncode}): {res.stderr.strip()}"
            )
            return {}
        out = res.stdout.strip()
        if not out:
            warn(
                "alsaucm dump json returned empty output for card "
                f"{card_index}"
            )
            return {}
        try:
            return json.loads(out)
        except ValueError:
            json_start = out.find("{")
            if json_start > 0:
                candidate = out[json_start:]
                try:
                    return json.loads(candidate)
                except ValueError:
                    pass
            warn(f"Failed to parse alsaucm dump json for card {card_index}")
            return {}

    def parse_alsaucm_json(
        self, dump: dict[str, object]
    ) -> dict[str, dict[str, object]]:
        """Parse verbs and devices from alsaucm dump json."""
        verbs = {}
        raw_verbs = dump.get("Verbs", {})
        if not isinstance(raw_verbs, dict):
            return verbs

        for verb_name, verb_body in raw_verbs.items():
            if not isinstance(verb_body, dict):
                continue
            verb = {
                "name": verb_name,
                "comment": verb_body.get("Comment", ""),
                "devices": [],
            }
            raw_devs = verb_body.get("Devices", {})
            if isinstance(raw_devs, dict):
                for dev_name, dev_body in raw_devs.items():
                    if not isinstance(dev_body, dict):
                        continue
                    vals = (
                        dev_body.get("Values", {})
                        if isinstance(dev_body.get("Values", {}), dict)
                        else {}
                    )
                    verb["devices"].append(
                        self._make_device(
                            dev_name,
                            comment=dev_body.get("Comment", ""),
                            values=vals,
                        )
                    )
            verbs[verb_name] = verb
        return verbs


def normalize_label(raw_value: str) -> str:
    """Normalize user/payload values for semantic checks."""
    return (raw_value or "").strip()


def is_na_label(raw_value: str) -> bool:
    """Return True when the provided value is empty or NA."""
    value = normalize_label(raw_value)
    return (not value) or (value.upper() == "NA")


def normalize_key(raw_value: str) -> str:
    """Normalize key names for soft matching across outputs."""
    return re.sub(r"[\s\-_]+", "", (raw_value or "").lower())


def resolve_choice(raw_value: str, choices: list[str]) -> str | None:
    """Resolve a value against choices using normalized matching."""
    target = normalize_key(raw_value)
    for choice in choices:
        if normalize_key(choice) == target:
            return choice
    return None


def _resolve_verb_entry(
    verb_map: dict[str, dict[str, object]], verb_name: str
) -> dict[str, object]:
    """Look up a verb entry with normalization fallback."""
    verb = verb_map.get(verb_name, {})
    if not verb:
        target = normalize_key(verb_name)
        for key_name, key_verb in verb_map.items():
            if normalize_key(key_name) == target:
                return key_verb
    return verb


def find_devices_for_verb(
    verb_map: dict[str, dict[str, object]], verb_name: str
) -> list[str]:
    """Return sorted unique device names for one verb."""
    verb = _resolve_verb_entry(verb_map, verb_name)
    devices = []
    for dev in verb.get("devices", []):
        name = dev.get("name")
        if name and name not in devices:
            devices.append(name)
    return sorted(devices)


def get_card_verb_map(
    card_manager: CardManager, parser: UCMJsonParser, card_index: int
) -> tuple[dict[str, dict[str, object]], list[str], bool]:
    """Get verb map, available verbs, and whether JSON verbs were available."""
    dump = parser.run_alsaucm_dump(card_index)
    verb_map = parser.parse_alsaucm_json(dump)
    verb_names = sorted(verb_map.keys())
    if verb_names:
        return verb_map, verb_names, True

    fallback_verbs = card_manager.list_alsaucm_verbs(card_index)
    for verb in fallback_verbs:
        candidate = (verb.get("name") or "").strip()
        if candidate and candidate not in verb_names:
            verb_names.append(candidate)
    return verb_map, verb_names, False


def fail_for_unknown_verb(
    card_label: str,
    verb_name: str,
    available_verbs: list[str],
    is_na_input: bool,
) -> None:
    """Print a verb validation failure with root-cause context."""
    if available_verbs:
        reason = "invalid verb" if is_na_input else "verb not found"
        print(
            f"[FAIL] {card_label} / {verb_name} -- {reason}. "
            f"Available verbs: {', '.join(available_verbs)}"
        )
        return
    print(
        f"[FAIL] {card_label} / {verb_name} -- "
        "no UCM verbs discovered for this card"
    )


def fail_for_unknown_device(
    card_label: str,
    resolved_verb: str,
    device_name: str,
    available_devices: list[str],
    is_na_input: bool,
) -> None:
    """Print a device validation failure with available choices."""
    if not available_devices:
        print(
            f"[FAIL] {card_label} / {resolved_verb} -- "
            "no UCM devices discovered for this verb"
        )
        return
    if is_na_input:
        print(
            f"[FAIL] {card_label} / {resolved_verb} -- invalid device. "
            f"Available devices: {', '.join(available_devices)}"
        )
        return
    print(
        f"[FAIL] {card_label} / {resolved_verb} / {device_name} -- "
        "device not found. Available devices: "
        f"{', '.join(available_devices)}"
    )


def print_resource_rows(rows: list[dict[str, str]]) -> None:
    """Print rows in variable-width block format."""
    for row in rows:
        print(f"SoundCard: {row['SoundCard']}")
        print(f"SoundNumber: {row['SoundNumber']}")
        print(f"Verbs: {row['Verbs']}")
        if "SinksDevice" in row:
            print(f"SinksDevice: {row['SinksDevice']}")
            print(f"SinksDeviceName: {row['SinksDeviceName']}")
        if "SourceDevice" in row:
            print(f"SourceDevice: {row['SourceDevice']}")
            print(f"SourceDeviceName: {row['SourceDeviceName']}")
        print("")


def parse_pairing_spec(spec: str | None) -> list[tuple[str, str]]:
    """Parse pairing spec 'SINK1:SRC1,SINK2:SRC2' into list of pairs."""
    pairs = []
    if not spec:
        return pairs
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    for part in parts:
        if ":" not in part:
            warn(f"Invalid pairing entry '{part}' (expected SINK:SOURCE)")
            continue
        sink, source = part.split(":", 1)
        sink = sink.strip()
        source = source.strip()
        if not sink or not source:
            warn(f"Invalid pairing entry '{part}' (empty sink/source)")
            continue
        pairs.append((sink, source))
    return pairs


def find_devices_for_verb_by_type(
    verb_map: dict[str, dict[str, object]],
    verb_name: str,
    dtype: str,
) -> list[str]:
    """Return sorted device names for one verb and one UCM device type."""
    verb = _resolve_verb_entry(verb_map, verb_name)
    devices = []
    for dev in verb.get("devices", []):
        name = dev.get("name")
        if name and dev.get("type") == dtype and name not in devices:
            devices.append(name)
    return sorted(devices)


def _device_meta_for_verb(
    verb_map: dict[str, dict[str, object]],
    verb_name: str,
    dtype: str,
) -> list[tuple[str, str]]:
    """Return sorted ``(name, comment)`` tuples for one verb / dtype.

    Mirrors :func:`find_devices_for_verb_by_type` but also surfaces the
    UCM ``Comment`` so resource rows can emit human-readable
    ``SinksDeviceName`` / ``SourceDeviceName`` fields.
    """
    verb = _resolve_verb_entry(verb_map, verb_name)
    seen = {}
    for dev in verb.get("devices", []):
        name = dev.get("name")
        if not name or dev.get("type") != dtype or name in seen:
            continue
        seen[name] = str(dev.get("comment") or "")
    return sorted(seen.items(), key=lambda nc: nc[0])


def make_resource_row(
    sound_card: str,
    sound_number: str,
    verbs: str,
    sink: tuple[str, str] | None = None,
    source: tuple[str, str] | None = None,
) -> dict[str, str]:
    """Build one resource row with optional device fields.

    ``sink`` / ``source`` are ``(name, comment)`` tuples produced by
    :func:`_device_meta_for_verb` (or assembled by callers that
    already know both halves).  The ``comment`` half populates the
    human-readable ``*DeviceName`` field; an empty comment falls back
    to the device name so the ``*DeviceName`` field is always present
    alongside its matching ``*Device`` key.  Pass ``None`` to omit a
    side entirely (e.g. for NA rows or single-device rows).
    """
    row = {
        "SoundCard": sound_card,
        "SoundNumber": sound_number,
        "Verbs": verbs,
    }
    if sink is not None:
        name, comment = sink
        row["SinksDevice"] = name
        row["SinksDeviceName"] = comment or name
    if source is not None:
        name, comment = source
        row["SourceDevice"] = name
        row["SourceDeviceName"] = comment or name
    return row


def _matched_loopback_rows(
    card_name: str,
    card_index: str,
    verb_name: str,
    pairs: list[tuple[str, str]],
    sink_meta: list[tuple[str, str]],
    source_meta: list[tuple[str, str]],
) -> list[dict[str, str]]:
    """Return loopback rows for pairs present in both device lists.

    ``pairs`` carries only the (sink_name, source_name) values that
    the user provided via ``--pairing``; ``sink_meta`` and
    ``source_meta`` are ``(name, comment)`` tuples from
    :func:`_device_meta_for_verb`.  We hydrate each CLI name with its
    matching comment here so :func:`make_resource_row` receives a
    self-contained ``(name, comment)`` tuple per side.
    """
    sink_lookup = dict(sink_meta)
    source_lookup = dict(source_meta)
    rows = []
    for sink_name, source_name in pairs:
        if sink_name not in sink_lookup or source_name not in source_lookup:
            continue
        rows.append(
            make_resource_row(
                card_name,
                card_index,
                verb_name,
                sink=(sink_name, sink_lookup[sink_name]),
                source=(source_name, source_lookup[source_name]),
            )
        )
    return rows


def _filtered_device_rows(
    card_name: str,
    card_index: str,
    verb_name: str,
    device_meta: list[tuple[str, str]],
    ignore: set[str],
    kind: str,
) -> list[dict[str, str]]:
    """Return device rows excluding names in *ignore*.

    ``device_meta`` is a list of ``(name, comment)`` tuples;
    ``kind`` is either ``"sink"`` or ``"source"`` and selects which
    side of :func:`make_resource_row` the tuple feeds into.  The
    whole ``(name, comment)`` is passed atomically so the
    ``*Device`` and ``*DeviceName`` fields stay paired by
    construction.
    """
    return [
        make_resource_row(
            card_name, card_index, verb_name, **{kind: (dev, comment)}
        )
        for dev, comment in device_meta
        if dev not in ignore
    ]


def build_resource_rows(
    card_manager: CardManager,
    parser: UCMJsonParser,
    mode: str | None,
    pairing_spec: str | None,
) -> list[dict[str, str]]:
    """Build flattened resource rows for Checkbox consumption.

    If *pairing_spec* is set, each SINK:SOURCE pair excludes that sink from
    sink-only output and that source from source-only output. ``loopback``
    mode emits only rows for pairs that exist on the verb. With no *mode* and
    a pairing spec, output merges loopback rows plus filtered sinks and
    sources (same rules).
    """
    rows = []
    cards = card_manager.list_cards()
    pairs = parse_pairing_spec(pairing_spec)
    sink_ignore = {pair[0] for pair in pairs}
    source_ignore = {pair[1] for pair in pairs}

    for card in cards:
        card_name = str(card.get("short_name", "UNKNOWN"))
        card_index = str(card.get("index", ""))
        verb_map, verb_names, has_json_verbs = get_card_verb_map(
            card_manager, parser, card.get("index")
        )

        if not verb_names or not has_json_verbs:
            if verb_names and not has_json_verbs:
                warn(
                    f"Card {card_index} has verbs from list fallback only; "
                    "emitting NA row because device map is unavailable "
                    "without JSON dump."
                )
            if mode is None:
                rows.append(make_resource_row(card_name, card_index, "NA"))
            continue

        for verb_name in verb_names:
            sink_meta = _device_meta_for_verb(
                verb_map, verb_name, UCM_TYPE_SINK
            )
            source_meta = _device_meta_for_verb(
                verb_map, verb_name, UCM_TYPE_SOURCE
            )

            if mode == "loopback":
                if not pairs:
                    warn(
                        "resource loopback requested but no "
                        "--pairing was provided; "
                        "skipping loopback rows"
                    )
                    continue
                rows.extend(
                    _matched_loopback_rows(
                        card_name,
                        card_index,
                        verb_name,
                        pairs,
                        sink_meta,
                        source_meta,
                    )
                )
                continue

            verb_rows = []

            if mode is None and pairs:
                verb_rows.extend(
                    _matched_loopback_rows(
                        card_name,
                        card_index,
                        verb_name,
                        pairs,
                        sink_meta,
                        source_meta,
                    )
                )

            if mode in (None, "sinks"):
                verb_rows.extend(
                    _filtered_device_rows(
                        card_name,
                        card_index,
                        verb_name,
                        sink_meta,
                        sink_ignore,
                        "sink",
                    )
                )

            if mode in (None, "sources"):
                verb_rows.extend(
                    _filtered_device_rows(
                        card_name,
                        card_index,
                        verb_name,
                        source_meta,
                        source_ignore,
                        "source",
                    )
                )

            if verb_rows:
                rows.extend(verb_rows)
            elif mode is None:
                rows.append(
                    make_resource_row(card_name, card_index, verb_name)
                )

    return rows


def run_resource(
    card_manager: CardManager,
    parser: UCMJsonParser,
    mode: str | None,
    pairing_spec: str | None,
) -> int:
    """Run the resource subcommand."""
    rows = build_resource_rows(card_manager, parser, mode, pairing_spec)
    print_resource_rows(rows)
    return 0


def resolve_pcm(pcm: str | None, card_index: int, card_name: str = "") -> str:
    """Expand UCM variables in a PCM path and return a usable device name.

    The UCM JSON dump provides the authoritative PCM device names via
    PlaybackPCM / CapturePCM.  UCM-level variable substitution and card
    name-to-index mapping are applied so the resulting device string
    works with tools like speaker-test and arecord. Examples:

    - ``_ucm0001.hw:mt8391evk,0`` (card 0, name ``mt8391evk``) gives
      ``hw:0,0``: ``_ucm\\d+\\.`` removes the ``_ucm0001.`` prefix and
      the card name becomes the card index.
    - ``hw:${CardId},2`` (card 1) gives ``hw:1,2``.
    """
    if not pcm:
        return f"hw:{card_index},0"
    pcm = re.sub(r"_ucm\d+\.", "", pcm)
    pcm = pcm.replace("${CardId}", str(card_index))
    if card_name:
        pcm = re.sub(
            rf"(hw:){re.escape(card_name)}",
            rf"\g<1>{card_index}",
            pcm,
        )
    return pcm


def parse_supported_formats(dump_text: str) -> list[str]:
    """Parse supported sample formats from --dump-hw-params output."""
    formats = []
    in_available_block = False
    for raw_line in (dump_text or "").splitlines():
        line = raw_line.strip()
        if line.startswith("FORMAT:"):
            after = line[len("FORMAT:") :].strip()
            tokens = re.findall(r"[A-Za-z0-9_]+", after)
            for tok in tokens:
                if tok not in formats:
                    formats.append(tok)
            in_available_block = False
            continue
        if line == "Available formats:":
            in_available_block = True
            continue
        if in_available_block:
            if line.startswith("-"):
                candidate = line.lstrip("-").strip()
                # Lines can be like "- S32_LE" or "- S16_LE (something)".
                tok_match = re.match(r"^([A-Za-z0-9_]+)", candidate)
                if tok_match:
                    tok = tok_match.group(1)
                    if tok not in formats:
                        formats.append(tok)
                continue
            # Stop once we leave the "Available formats" list.
            if not line:
                in_available_block = False
            elif not line.startswith("-"):
                in_available_block = False
    return formats


_PROBE_SPECS = {
    UCM_TYPE_SINK: (["aplay"], ["--dump-hw-params", "/dev/zero"], "aplay"),
    UCM_TYPE_SOURCE: (["arecord"], ["--dump-hw-params"], "arecord"),
}


def probe_supported_formats(resolved_pcm: str, stream_type: str) -> list[str]:
    """Probe supported formats for the provided PCM device."""
    spec = _PROBE_SPECS.get(stream_type)
    if spec is None:
        return []
    tool_argv, extra_args, tool_name = spec
    cmd = tool_argv + ["-D", resolved_pcm] + extra_args
    res = subprocess.run(
        cmd, capture_output=True, text=True, timeout=TIMEOUT_ALSAUCM_QUERY
    )
    formats = parse_supported_formats(f"{res.stdout}\n{res.stderr}")
    if not formats and res.returncode != 0:
        warn(
            f"{tool_name} --dump-hw-params did not reveal formats for "
            f"{resolved_pcm} (rc={res.returncode})"
        )
    return formats


def pick_sample_format(
    formats: list[str], preferred: str = DEFAULT_SAMPLE_FORMAT
) -> str:
    """Pick preferred format if available, otherwise first supported format."""
    if not formats:
        return preferred
    if preferred in formats:
        return preferred
    return formats[0]


def get_device_info(
    verb_map: dict[str, dict[str, object]],
    verb_name: str,
    device_name: str,
) -> tuple[str, str | None, str]:
    """Return (type, pcm, channels) for a device in verb_map."""
    verb = _resolve_verb_entry(verb_map, verb_name)
    for dev in verb.get("devices", []):
        if dev.get("name") == device_name:
            return (
                dev.get("type", UCM_TYPE_UNKNOWN),
                dev.get("pcm"),
                dev.get("channels", "2"),
            )
    return UCM_TYPE_UNKNOWN, None, "2"


@dataclass
class DeviceStreamPlan:
    """PCM, channels, and sample format for one device side."""

    stream_type: str
    resolved_pcm: str
    channels: str
    test_int: int
    declared: int | None
    sample_format: str


def build_device_stream_plan(
    verb_map: dict[str, dict[str, object]],
    verb_name: str,
    device_name: str,
    card_index: int,
    card_name: str,
    dry_run: bool,
) -> DeviceStreamPlan:
    """Resolve PCM, channels, and sample format for one device side.

    Encapsulates the five-step setup sequence
    (``get_device_info`` -> ``cap_test_channels`` -> ``resolve_pcm``
    -> ``probe_supported_formats`` + ``pick_sample_format``) that
    both ``SingleDeviceRunner`` and ``LoopbackRunner`` repeat per
    device side.
    """
    stream_type, raw_pcm, raw_channels = get_device_info(
        verb_map, verb_name, device_name
    )
    channels, test_int, declared = cap_test_channels(raw_channels)
    resolved_pcm = resolve_pcm(raw_pcm, card_index, card_name)
    sample_format = DEFAULT_SAMPLE_FORMAT
    if not dry_run and stream_type in (UCM_TYPE_SINK, UCM_TYPE_SOURCE):
        supported = probe_supported_formats(resolved_pcm, stream_type)
        sample_format = pick_sample_format(supported, DEFAULT_SAMPLE_FORMAT)
    return DeviceStreamPlan(
        stream_type=stream_type,
        resolved_pcm=resolved_pcm,
        channels=channels,
        test_int=test_int,
        declared=declared,
        sample_format=sample_format,
    )


def cap_test_channels(declared: object) -> tuple[str, int, int | None]:
    """Clamp the UCM-declared channel count to ``MAX_TEST_CHANNELS``.

    Returns ``(test_channels_str, test_channels_int, declared_int)``.

    ``declared`` is whatever UCM gave us (typically a ``str`` from
    ``Playback/CaptureChannels``).  When ``declared`` cannot be parsed
    as an int (missing / non-numeric), the third return value is
    ``None`` so the log helper can report "no UCM declaration"
    instead of fabricating a number.  Parseable values are clamped to
    ``[1, MAX_TEST_CHANNELS]`` so we never call ``speaker-test -c 0``
    and never exceed the test cap.  The first two return values are
    the same number in ``str`` and ``int`` form -- ``str`` is what the
    speaker-test / arecord command builders take, ``int`` is what
    :func:`_log_channel_cap` and the loopback WAV size check need.
    """
    try:
        declared_int = int(declared)
    except (TypeError, ValueError):
        declared_int = None
    if declared_int is None:
        test_int = MAX_TEST_CHANNELS
    else:
        test_int = min(max(declared_int, 1), MAX_TEST_CHANNELS)
    return str(test_int), test_int, declared_int


def _log_channel_cap(
    device_label: str, declared: int | None, test: int
) -> None:
    """Print a single ``[INFO]`` line describing the cap decision.

    Distinguishes three "test != declared" reasons so the user can
    see why the chosen channel count differs from what UCM said:

    - ``declared is None``     -> UCM did not declare any channel
      count (we defaulted to ``MAX_TEST_CHANNELS``).
    - ``declared > MAX_TEST_CHANNELS`` -> capped down.
    - ``declared < 1``         -> clamped up to a minimum of ``1``.
    - otherwise                -> the two values agree.
    """
    if declared is None:
        print(
            f"[INFO] {device_label}: UCM did not declare a channel count; "
            f"using {test} for testing (default = {MAX_TEST_CHANNELS})"
        )
        return

    declared_word = "channel" if declared == 1 else "channels"
    if declared > MAX_TEST_CHANNELS:
        print(
            f"[INFO] {device_label}: UCM declares {declared} {declared_word}; "
            f"using {test} for testing (capped at max {MAX_TEST_CHANNELS})"
        )
    elif declared < 1:
        print(
            f"[INFO] {device_label}: UCM declares {declared} {declared_word}; "
            f"using {test} for testing (clamped to min 1)"
        )
    else:
        print(
            f"[INFO] {device_label}: UCM declares {declared} {declared_word}; "
            f"using {test} for testing"
        )


class AlsaUcmCli:
    """Variadic alsaucm subprocess wrapper for apply / cleanup / format.

    Replaces the former six standalone functions with N-device methods.
    Single-device calls are just the 1-device case of the same logic.
    """

    @staticmethod
    def argv(card_index: int, *set_pairs: tuple[str, str]) -> list[str]:
        """Build an alsaucm command with ``set key value`` pairs."""
        cmd = ["alsaucm", "-c", str(card_index)]
        for key, val in set_pairs:
            cmd.extend(["set", key, val])
        return cmd

    @staticmethod
    def fmt(card_index: str, *set_pairs: tuple[str, str]) -> str:
        """Format an alsaucm command string for display."""
        parts = ["alsaucm", "-c", card_index]
        for key, val in set_pairs:
            parts.extend(["set", key, val])
        return " ".join(parts)

    @staticmethod
    def apply(
        card_index: int, verb: str, *devices: str
    ) -> subprocess.CompletedProcess:
        """Apply UCM verb and enable one or more devices.

        For multi-device calls, falls back to sequential ``_enadev``
        enables when the single-call approach fails.
        """
        pairs = [("_verb", verb)] + [("_enadev", d) for d in devices]
        res = subprocess.run(
            AlsaUcmCli.argv(card_index, *pairs),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_ALSAUCM_APPLY,
        )
        if res.returncode == 0 or len(devices) <= 1:
            return res

        warn(
            f"Loopback alsaucm apply (single-call) failed "
            f"(rc={res.returncode}); trying sequential _enadev enable "
            "without re-setting the verb."
        )
        steps = [[("_verb", verb), ("_enadev", devices[0])]]
        steps += [[("_enadev", dev)] for dev in devices[1:]]
        for step in steps:
            res = subprocess.run(
                AlsaUcmCli.argv(card_index, *step),
                capture_output=True,
                text=True,
                timeout=TIMEOUT_ALSAUCM_APPLY,
            )
            if res.returncode != 0:
                return res
        return res

    @staticmethod
    def cleanup(card_index: int, *devices: str) -> None:
        """Best-effort cleanup: disable one or more devices.

        Tries a single multi-``_disdev`` call first; falls back to
        sequential disables on failure.
        """
        pairs = [("_disdev", d) for d in devices]
        rc = subprocess.run(
            AlsaUcmCli.argv(card_index, *pairs),
            capture_output=True,
            timeout=TIMEOUT_ALSAUCM_QUERY,
        ).returncode
        if rc == 0 or len(devices) <= 1:
            if rc != 0:
                warn(f"cleanup _disdev {devices[0]} returned rc={rc}")
            return
        warn(
            f"cleanup loopback multi _disdev returned rc={rc}; "
            "trying sequential disables."
        )
        for dev in devices:
            single_rc = subprocess.run(
                AlsaUcmCli.argv(card_index, ("_disdev", dev)),
                capture_output=True,
                timeout=TIMEOUT_ALSAUCM_QUERY,
            ).returncode
            if single_rc != 0:
                warn(f"cleanup _disdev {dev} returned rc={single_rc}")


def save_alsa_state(card_index: int) -> str | None:
    """Save ALSA mixer state to a temp file via alsactl store."""
    fd, path = tempfile.mkstemp(
        prefix=f"alsa_state_card{card_index}_", suffix=".state"
    )
    os.close(fd)
    res = subprocess.run(
        ["alsactl", "-f", path, "store", str(card_index)],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_ALSAUCM_QUERY,
    )
    if res.returncode != 0:
        warn(
            f"alsactl store failed (rc={res.returncode}): "
            f"{res.stderr.strip()}"
        )
        os.unlink(path)
        return None
    return path


def restore_alsa_state(card_index: int, state_file: str) -> bool:
    """Restore ALSA mixer state from a saved file via alsactl restore."""
    try:
        res = subprocess.run(
            ["alsactl", "-f", state_file, "restore", str(card_index)],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_ALSAUCM_QUERY,
        )
    finally:
        os.unlink(state_file)
    if res.returncode != 0:
        warn(
            f"alsactl restore failed (rc={res.returncode}): "
            f"{res.stderr.strip()}"
        )
        return False
    return True


class StreamCommandBuilder:
    """Build and run speaker-test / arecord commands from shared argv logic."""

    @staticmethod
    def speaker_argv(
        pcm: str, channels: str, sample_format: str, loops: int = 1
    ) -> list[str]:
        """Build speaker-test argv."""
        return [
            "speaker-test",
            "-D",
            pcm,
            "-c",
            str(channels),
            "-F",
            sample_format,
            "-r",
            str(DEFAULT_SAMPLE_RATE),
            "-t",
            "wav",
            "-l",
            str(loops),
        ]

    @staticmethod
    def arecord_argv(
        pcm: str,
        channels: str,
        sample_format: str,
        duration: int,
        output_path: str,
    ) -> list[str]:
        """Build arecord argv."""
        return [
            "arecord",
            "-D",
            pcm,
            "-c",
            str(channels),
            "-f",
            sample_format,
            "-r",
            str(DEFAULT_SAMPLE_RATE),
            "-d",
            str(duration),
            "-t",
            "wav",
            output_path,
        ]

    @staticmethod
    def fmt_speaker_cmd(
        pcm: str, channels: str, sample_format: str, loops: int = 1
    ) -> str:
        """Format a speaker-test command string for display."""
        return " ".join(
            StreamCommandBuilder.speaker_argv(
                pcm, channels, sample_format, loops
            )
        )

    @staticmethod
    def fmt_arecord_cmd(
        pcm: str,
        channels: str,
        sample_format: str,
        duration: int,
        output_path: str,
    ) -> str:
        """Format an arecord command string for display."""
        return " ".join(
            StreamCommandBuilder.arecord_argv(
                pcm, channels, sample_format, duration, output_path
            )
        )

    @staticmethod
    def run_speaker(
        pcm: str,
        channels: str,
        sample_format: str,
        loops: int = 1,
        timeout: int = 30,
    ) -> subprocess.CompletedProcess:
        """Run speaker-test."""
        return subprocess.run(
            StreamCommandBuilder.speaker_argv(
                pcm, channels, sample_format, loops
            ),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    @staticmethod
    def run_arecord(
        pcm: str,
        channels: str,
        sample_format: str,
        duration: int,
        output_path: str,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess:
        """Run arecord."""
        return subprocess.run(
            StreamCommandBuilder.arecord_argv(
                pcm, channels, sample_format, duration, output_path
            ),
            capture_output=True,
            text=True,
            timeout=timeout or duration + 20,
        )


def run_stream_test(
    resolved_pcm: str,
    stream_type: str,
    channels: str,
    sample_format: str,
    record_path: str | None = None,
) -> subprocess.CompletedProcess:
    """Run a short audio stream to verify the device works.

    A Sink plays a speaker-test WAV once. A Source records
    ``DEFAULT_RECORD_DURATION`` seconds into *record_path*.
    """
    if stream_type == UCM_TYPE_SINK:
        return StreamCommandBuilder.run_speaker(
            resolved_pcm, channels, sample_format
        )
    res = StreamCommandBuilder.run_arecord(
        resolved_pcm,
        channels,
        sample_format,
        DEFAULT_RECORD_DURATION,
        record_path,
        timeout=30,
    )
    if res.returncode == 0:
        print(f"[INFO] Recorded file saved to: {record_path}")
        print(f"To play it: aplay {record_path}")
    else:
        warn(
            f"arecord failed (rc={res.returncode}); "
            f"recording file may exist: {record_path}"
        )
    return res


def resolve_card_and_verb(
    card_selector: str,
    verb_input: str,
    card_manager: CardManager,
    parser: UCMJsonParser,
) -> TestContext | None:
    """Resolve and validate card + verb, printing failures.

    Returns a TestContext on success, None on validation failure.
    """
    card_obj = card_manager.get_card(card_selector)
    if not card_obj:
        print(
            f"[FAIL] Card {card_selector} could not be resolved from "
            "discovered cards."
        )
        return None
    card_name = card_obj.get("short_name", "UNKNOWN")
    card_index = card_obj.get("index")
    resolved_card = str(card_index)
    card_label = f"Card {resolved_card} ({card_name})"
    verb_name = normalize_label(verb_input)
    verb_map, available_verbs, _has_json = get_card_verb_map(
        card_manager, parser, card_index
    )
    is_na = is_na_label(verb_name)
    resolved_verb = (
        None if is_na else resolve_choice(verb_name, available_verbs)
    )
    if not resolved_verb:
        fail_for_unknown_verb(
            card_label,
            verb_name,
            available_verbs,
            is_na_input=is_na,
        )
        return None
    return TestContext(
        card_name=card_name,
        card_index=card_index,
        resolved_card=resolved_card,
        card_label=card_label,
        verb_map=verb_map,
        resolved_verb=resolved_verb,
    )


def resolve_device_for_test(
    card_label: str,
    resolved_verb: str,
    device_input: str,
    verb_map: dict[str, dict[str, object]],
    available_devices: list[str] | None = None,
) -> str | None:
    """Resolve and validate a device name, printing failures.

    Returns resolved device name on success, None on validation failure.
    """
    device_name = normalize_label(device_input)
    if available_devices is None:
        available_devices = find_devices_for_verb(verb_map, resolved_verb)
    is_na = is_na_label(device_name)
    resolved = (
        None
        if is_na or not available_devices
        else resolve_choice(device_name, available_devices)
    )
    if not resolved:
        fail_for_unknown_device(
            card_label,
            resolved_verb,
            device_name,
            available_devices,
            is_na_input=is_na,
        )
        return None
    return resolved


class AlsaStateGuard:
    """Context manager: save ALSA mixer state on enter, restore on exit.

    Uses ``alsactl store`` to snapshot the mixer before a test and
    ``alsactl restore`` on exit.  When the snapshot is unavailable the
    caller-provided *fallback_cleanup* callable is invoked instead.
    Set *apply_succeeded* to ``True`` after the UCM apply step so
    that fallback cleanup is only attempted when the device was
    actually enabled.
    """

    _PLACEHOLDER_TPL = "/tmp/alsa_state_card{0}_XXXX.state"

    def __init__(
        self,
        card_index: int,
        resolved_card: str,
        dry_run: bool,
        fallback_cleanup: Callable,
    ) -> None:
        """Initialise guard with card details and cleanup strategy."""
        self.card_index = card_index
        self.resolved_card = resolved_card
        self.dry_run = dry_run
        self.fallback_cleanup = fallback_cleanup
        self.tag = "[DRY-RUN] " if dry_run else ""
        self.state_file: str | None = None
        self.apply_succeeded = False

    def _effective_path(self) -> str | None:
        """Return state file path, or a placeholder when dry-running."""
        if self.dry_run:
            return self._PLACEHOLDER_TPL.format(self.resolved_card)
        return self.state_file

    def _log_alsactl(self, action: str) -> None:
        """Print the alsactl command that is (or would be) executed."""
        path = self._effective_path()
        if path:
            print(f"{self.tag}alsactl -f {path} {action} {self.resolved_card}")

    def __enter__(self) -> AlsaStateGuard:
        """Save ALSA mixer state (or print dry-run placeholder)."""
        if not self.dry_run:
            self.state_file = save_alsa_state(self.card_index)
            if not self.state_file:
                warn("Could not save ALSA state; will use basic cleanup only")
                return self
        self._log_alsactl("store")
        return self

    def __exit__(self, *exc_info: object) -> Literal[False]:
        """Restore ALSA mixer state (or run fallback cleanup)."""
        if self.dry_run or self.state_file:
            self._log_alsactl("restore")
            if self.state_file:
                restore_alsa_state(self.card_index, self.state_file)
        elif self.apply_succeeded:
            self.fallback_cleanup()
        return False


class BaseUcmTestRunner(ABC):
    """Template for UCM test runners with shared card/verb/apply lifecycle."""

    def __init__(
        self, card_manager: CardManager, parser: UCMJsonParser
    ) -> None:
        """Initialise with shared card manager and UCM parser."""
        self.card_manager = card_manager
        self.parser = parser

    def run(self, args: argparse.Namespace) -> int:
        """Resolve card + verb, then delegate to subclass."""
        ctx = resolve_card_and_verb(
            args.card,
            args.verb,
            self.card_manager,
            self.parser,
        )
        if ctx is None:
            return 1
        return self._execute(ctx, args)

    @abstractmethod
    def _execute(self, ctx: TestContext, args: argparse.Namespace) -> int:
        """Subclass hook: run the test after card+verb resolution."""

    @staticmethod
    def _print_apply_failure(
        scope_label: str, apply_rc: int, apply_err: str
    ) -> None:
        """Print [FAIL] for alsaucm apply with optional stderr."""
        print(f"[FAIL] {scope_label} -- alsaucm apply exit code {apply_rc}")
        if (apply_err or "").strip():
            print(f"[FAIL] apply stderr: {apply_err.strip()}")

    @staticmethod
    def _print_stream_failure(
        scope_label: str, tool_label: str, rc: int, stderr: str
    ) -> None:
        """Print [FAIL] for a stream tool exit code with optional stderr."""
        print(f"[FAIL] {scope_label} -- {tool_label} exit code {rc}")
        if (stderr or "").strip():
            print(f"[FAIL] {tool_label} stderr: {stderr.strip()}")

    def _apply_devices(
        self,
        ctx: TestContext,
        guard: AlsaStateGuard,
        devices: list[str],
        dry_run: bool,
        tag: str,
    ) -> bool:
        """Print, apply, and handle failure for one or more devices.

        Returns ``True`` on success (or dry-run), ``False`` on failure.
        Callers turn ``False`` into ``return 1``.
        """
        pairs = [("_verb", ctx.resolved_verb)]
        pairs.extend(("_enadev", d) for d in devices)
        apply_cmd_str = AlsaUcmCli.fmt(ctx.resolved_card, *pairs)
        print(f"{tag}{apply_cmd_str}")
        if not dry_run:
            res = AlsaUcmCli.apply(ctx.card_index, ctx.resolved_verb, *devices)
            if res.returncode != 0:
                scope = f"{ctx.card_label} / {ctx.resolved_verb}"
                if len(devices) == 1:
                    scope = f"{scope} / {devices[0]}"
                self._print_apply_failure(scope, res.returncode, res.stderr)
                return False
            guard.apply_succeeded = True
        return True

    @staticmethod
    def _mk_record_tempfile(
        prefix: str, dry_run: bool, placeholder: str
    ) -> tuple[str | None, str]:
        """Create a temp WAV file, or return placeholder for dry-run."""
        if dry_run:
            return None, placeholder
        fd, path = tempfile.mkstemp(prefix=prefix, suffix=".wav")
        os.close(fd)
        return path, path


class SingleDeviceRunner(BaseUcmTestRunner):
    """Run a single Checkbox test invocation for one resource row."""

    def _execute(self, ctx: TestContext, args: argparse.Namespace) -> int:
        """Resolve one device, apply UCM, run stream test."""
        resolved_device = resolve_device_for_test(
            ctx.card_label, ctx.resolved_verb, args.device, ctx.verb_map
        )
        if resolved_device is None:
            return 1

        dry_run = args.dry_run
        tag = "[DRY-RUN] " if dry_run else ""
        plan = build_device_stream_plan(
            ctx.verb_map,
            ctx.resolved_verb,
            resolved_device,
            ctx.card_index,
            ctx.card_name,
            dry_run,
        )

        guard = AlsaStateGuard(
            ctx.card_index,
            ctx.resolved_card,
            dry_run,
            lambda: AlsaUcmCli.cleanup(ctx.card_index, resolved_device),
        )
        with guard:
            if not self._apply_devices(
                ctx, guard, [resolved_device], dry_run, tag
            ):
                return 1

            record_path, record_display = self._mk_record_tempfile(
                "alsa_checkbox_record_",
                dry_run or plan.stream_type != UCM_TYPE_SOURCE,
                f"/tmp/alsa_checkbox_record_card{ctx.resolved_card}_XXXX.wav",
            )

            if plan.stream_type == UCM_TYPE_SINK:
                stream_cmd_str = StreamCommandBuilder.fmt_speaker_cmd(
                    plan.resolved_pcm, plan.channels, plan.sample_format
                )
            elif plan.stream_type == UCM_TYPE_SOURCE:
                stream_cmd_str = StreamCommandBuilder.fmt_arecord_cmd(
                    plan.resolved_pcm,
                    plan.channels,
                    plan.sample_format,
                    DEFAULT_RECORD_DURATION,
                    record_display,
                )
            else:
                stream_cmd_str = None

            if stream_cmd_str:
                _log_channel_cap(
                    resolved_device,
                    plan.declared,
                    plan.test_int,
                )
                print(f"{tag}{stream_cmd_str}")
            else:
                warn(
                    f"Device {resolved_device} has no PlaybackPCM/CapturePCM; "
                    "skipping stream test"
                )

            scope = (
                f"{ctx.card_label} / {ctx.resolved_verb} / {resolved_device}"
            )
            if not dry_run and stream_cmd_str:
                res = run_stream_test(
                    plan.resolved_pcm,
                    plan.stream_type,
                    plan.channels,
                    plan.sample_format,
                    record_path=record_path,
                )
                if res.returncode != 0:
                    self._print_stream_failure(
                        scope, "stream test", res.returncode, res.stderr
                    )
                    return 1

            suffix = " (dry-run)" if dry_run else ""
            if not stream_cmd_str:
                suffix = f" (no stream test){suffix}"
            print(f"[PASS] {scope}{suffix}")
            return 0


class LoopbackRunner(BaseUcmTestRunner):
    """Run a threaded loopback test (playback + record concurrently)."""

    def _execute(self, ctx: TestContext, args: argparse.Namespace) -> int:
        """Resolve sink+source, apply UCM, run concurrent streams."""
        sink_devices = find_devices_for_verb_by_type(
            ctx.verb_map, ctx.resolved_verb, UCM_TYPE_SINK
        )
        source_devices = find_devices_for_verb_by_type(
            ctx.verb_map, ctx.resolved_verb, UCM_TYPE_SOURCE
        )
        resolved_sink = resolve_device_for_test(
            ctx.card_label,
            ctx.resolved_verb,
            args.sink_device,
            ctx.verb_map,
            sink_devices,
        )
        if resolved_sink is None:
            return 1
        resolved_source = resolve_device_for_test(
            ctx.card_label,
            ctx.resolved_verb,
            args.source_device,
            ctx.verb_map,
            source_devices,
        )
        if resolved_source is None:
            return 1

        duration = int(getattr(args, "duration", 10))
        speaker_loops = int(getattr(args, "speaker_loops", 2))
        dry_run = bool(getattr(args, "dry_run", False))
        tag = "[DRY-RUN] " if dry_run else ""

        sink_plan = build_device_stream_plan(
            ctx.verb_map,
            ctx.resolved_verb,
            resolved_sink,
            ctx.card_index,
            ctx.card_name,
            dry_run,
        )
        source_plan = build_device_stream_plan(
            ctx.verb_map,
            ctx.resolved_verb,
            resolved_source,
            ctx.card_index,
            ctx.card_name,
            dry_run,
        )

        record_path, record_display = self._mk_record_tempfile(
            "alsa_checkbox_loopback_record_",
            dry_run,
            "/tmp/alsa_checkbox_loopback_record_card"
            f"{ctx.resolved_card}_XXXX.wav",
        )

        guard = AlsaStateGuard(
            ctx.card_index,
            ctx.resolved_card,
            dry_run,
            lambda: AlsaUcmCli.cleanup(
                ctx.card_index, resolved_sink, resolved_source
            ),
        )
        with guard:
            if not self._apply_devices(
                ctx, guard, [resolved_sink, resolved_source], dry_run, tag
            ):
                return 1

            speaker_cmd = StreamCommandBuilder.fmt_speaker_cmd(
                sink_plan.resolved_pcm,
                sink_plan.channels,
                sink_plan.sample_format,
                speaker_loops,
            )
            arecord_cmd = StreamCommandBuilder.fmt_arecord_cmd(
                source_plan.resolved_pcm,
                source_plan.channels,
                source_plan.sample_format,
                duration,
                record_display,
            )
            _log_channel_cap(
                resolved_sink, sink_plan.declared, sink_plan.test_int
            )
            print(f"{tag}{speaker_cmd}")
            _log_channel_cap(
                resolved_source, source_plan.declared, source_plan.test_int
            )
            print(f"{tag}{arecord_cmd}")

            if dry_run:
                print(
                    f"[PASS] {ctx.card_label} / {ctx.resolved_verb} / "
                    "loopback (dry-run)"
                )
                return 0

            return self._run_concurrent_streams(
                ctx,
                sink_plan,
                speaker_loops,
                source_plan,
                duration,
                record_path,
            )

    def _run_concurrent_streams(
        self,
        ctx: TestContext,
        sink_plan: DeviceStreamPlan,
        speaker_loops: int,
        source_plan: DeviceStreamPlan,
        duration: int,
        record_path: str,
    ) -> int:
        """Run playback and capture at the same time, then check the WAV."""
        scope = f"{ctx.card_label} / {ctx.resolved_verb}"
        with ThreadPoolExecutor(max_workers=2) as pool:
            play = pool.submit(
                StreamCommandBuilder.run_speaker,
                sink_plan.resolved_pcm,
                sink_plan.channels,
                sink_plan.sample_format,
                speaker_loops,
                timeout=max(30, speaker_loops * 5),
            )
            cap = pool.submit(
                StreamCommandBuilder.run_arecord,
                source_plan.resolved_pcm,
                source_plan.channels,
                source_plan.sample_format,
                duration,
                record_path,
            )
        for tool, res in (("speaker-test", play), ("arecord", cap)):
            res = res.result()
            if res.returncode != 0:
                self._print_stream_failure(
                    scope, tool, res.returncode, res.stderr
                )
                return 1

        if not record_path or not os.path.exists(record_path):
            print(f"[FAIL] {scope} -- loopback capture file missing")
            return 1

        bytes_per_sample = 2
        if (
            "S24" in source_plan.sample_format
            or "S32" in source_plan.sample_format
        ):
            bytes_per_sample = 4
        try:
            cap_channels_int = int(source_plan.channels)
        except ValueError:
            cap_channels_int = MAX_TEST_CHANNELS
        expected_min = (
            duration
            * DEFAULT_SAMPLE_RATE
            * cap_channels_int
            * bytes_per_sample
        ) // WAV_MIN_SIZE_DIVISOR
        actual_size = os.path.getsize(record_path)
        if actual_size < expected_min:
            print(
                f"[FAIL] {scope} -- recorded WAV too small "
                f"({actual_size} bytes, min {expected_min})"
            )
            return 1

        print(f"[PASS] {scope} / loopback / wav saved: {record_path}")
        print(f"To play it: aplay {record_path}")
        return 0


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
    parser_desc = "Checkbox ALSA UCM semi-auto helper"
    parser = argparse.ArgumentParser(description=parser_desc)
    sub = parser.add_subparsers(dest="command_name")

    p_resource = sub.add_parser("resource", help="Emit Checkbox resource rows")
    p_resource.add_argument(
        "mode",
        nargs="?",
        default=None,
        choices=["sinks", "sources", "loopback"],
        help="Filter mode: sinks, sources, or loopback (omit for all)",
    )
    p_resource.add_argument(
        "--pairing",
        default=None,
        metavar="SPEC",
        help=(
            "SINK:SOURCE pairs (comma-separated). For sinks/sources modes, "
            "paired devices are omitted from those lists; for loopback mode, "
            "only these pairs are emitted (required). Bare resource with "
            "this flag merges loopback + filtered sinks + sources. "
            "Example: 'Speaker:Mic,Headphones:Mic2'"
        ),
    )
    p_resource.add_argument(
        "--loopback-pairing",
        dest="pairing",
        default=None,
        metavar="SPEC",
        help=argparse.SUPPRESS,
    )
    p_resource.set_defaults(command_name="resource")

    p_test = sub.add_parser("test", help="Run one row test")
    p_test.add_argument(
        "-c",
        "--card",
        required=True,
        help="SoundNumber value from resource row",
    )
    p_test.add_argument(
        "-v",
        "--verb",
        required=True,
        help="Verb value from resource row",
    )
    p_test.add_argument(
        "-d",
        "--device",
        required=True,
        help="Device value from resource row",
    )
    p_test.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate logic and print commands without running subprocesses",
    )
    p_test.set_defaults(command_name="test")

    p_loop = sub.add_parser(
        "loopback-test", help="Run threaded loopback playback+record"
    )
    p_loop.add_argument(
        "-c",
        "--card",
        required=True,
        help="SoundNumber value from resource row",
    )
    p_loop.add_argument(
        "-v",
        "--verb",
        required=True,
        help="Verb value from resource row",
    )
    p_loop.add_argument(
        "--sink-device",
        required=True,
        help="Sink device value from resource row",
    )
    p_loop.add_argument(
        "--source-device",
        required=True,
        help="Source device value from resource row",
    )
    p_loop.add_argument(
        "--duration",
        type=int,
        default=10,
        help="Capture duration in seconds (arecord -d)",
    )
    p_loop.add_argument(
        "--speaker-loops",
        type=int,
        default=2,
        help="speaker-test -l loop count",
    )
    p_loop.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate logic and print commands without running subprocesses",
    )
    p_loop.set_defaults(command_name="loopback-test")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Program entry point with injectable argv for unit tests."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command_name", None):
        parser.print_help()
        return 1

    card_manager = CardManager()
    ucm_parser = UCMJsonParser()

    if args.command_name == "resource":
        return run_resource(card_manager, ucm_parser, args.mode, args.pairing)
    if args.command_name == "test":
        return SingleDeviceRunner(card_manager, ucm_parser).run(args)
    if args.command_name == "loopback-test":
        return LoopbackRunner(card_manager, ucm_parser).run(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
