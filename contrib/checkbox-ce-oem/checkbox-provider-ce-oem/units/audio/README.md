# ALSA UCM tests

The ALSA UCM tests are semi-automatic tests for sound cards that expose ALSA
Use Case Manager verbs and devices. The helper discovers UCM Sink devices,
Source devices, and configured Sink:Source loopback pairs, then generates
Checkbox jobs for each resource row.

The jobs run the required ALSA commands automatically, but a human must confirm
the final audio result:

- Sink tests: confirm that the playback sound is audible and clear.
- Source tests: play or copy the recorded WAV file and confirm the capture is
  clear.
- Loopback tests: play or copy the recorded WAV file and confirm the loopback
  audio quality is correct.

## Install the ALSA tools

The tests use the ALSA tools, library and UCM configuration of the system
under test. They do not use the copies in the Checkbox snap. Install them
before the test.

The helper runs `alsaucm`, `alsactl`, `aplay`, `arecord` and `speaker-test`
with the system environment. The Checkbox snap sets `LD_LIBRARY_PATH`,
`ALSA_CONFIG_PATH` and `ALSA_PLUGIN_DIR` to its own ALSA library and
configuration, so the helper removes them. It also searches the tools only in
`/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin`.
If a tool is missing, the job fails with
`[FAIL] <tool> is not installed on the system`.

### Classic Ubuntu (desktop and server)

Install the Debian packages:

```bash
sudo apt install alsa-utils alsa-ucm-conf
```

Then examine that the tools come from the system:

```bash
command -v aplay    # /usr/bin/aplay
```

### Ubuntu Core

Ubuntu Core uses three snaps:

| Snap | Gives |
| --- | --- |
| `alsa-utils` | the ALSA tools (`alsaucm`, `alsactl`, `aplay`, `arecord`, `speaker-test`) |
| `alsa-lib` | `libasound` and the ALSA plugins, through the `alsa-lib` content interface |
| `alsa-ucm-conf` | the UCM2 configuration, through the `ucm-conf` content interface |

These snaps are not published yet. When they are available, install them and
connect the interfaces:

```bash
sudo snap install alsa-lib alsa-ucm-conf alsa-utils
sudo snap connect alsa-utils:alsa
sudo snap connect alsa-utils:alsa-lib alsa-lib:alsa-lib
sudo snap connect alsa-utils:ucm-conf alsa-ucm-conf:ucm-conf
```

Then make the tool commands available in `/snap/bin` with their usual names:

```bash
for t in alsaucm alsactl aplay arecord speaker-test; do
    sudo snap alias "alsa-utils.$t" "$t"
done
command -v aplay    # /snap/bin/aplay
```

If you install a snap with `--dangerous`, add its name to
`SNAP_CONFINEMENT_ALLOWLIST` in the device launcher.

## Give the normal user access to the sound devices

The jobs run as the normal user of Checkbox, not as root. The ALSA tools open
the sound devices in `/dev/snd/`. These devices belong to the `audio` group
(mode `0660`). Thus the normal user must have access to them before the test.

The usual setup is a seat session: the normal user is logged in on the local
seat of the device (the screen, or a local console such as `tty1`).
systemd-logind then gives the user access to `/dev/snd/` with an ACL. Keep
this session active during the test. An SSH login does not give this access.

If the device has no seat session, add the normal user to the `audio` group,
then log in again:

```bash
sudo usermod -aG audio "$USER"
```

Then examine the access as the normal user:

```bash
ls -l /dev/snd/controlC0    # "+" after the mode = seat ACL
id -nG                      # or the list contains "audio"
alsaucm -c 0 list _verbs    # lists the verbs, no "failed to open sound card"
```

If the normal user has no access, `alsaucm` cannot open the card. Then the
resource jobs give no rows and the detect jobs fail.

## Test plan

Run the plan directly (it is also nested in `ce-oem-manual`):

```text
ce-oem-audio-alsa-ucm-manual
```

This plan is not included in `ce-oem-audio-automated`. It includes the jobs
`ce-oem-audio/alsa-ucm-detect-sink` and `ce-oem-audio/alsa-ucm-detect-source`,
and these template IDs:

```text
ce-oem-audio/alsa-ucm-sink-tests
ce-oem-audio/alsa-ucm-source-tests
ce-oem-audio/alsa-ucm-loopback-tests
```

`ce-oem-audio/alsa-ucm-detect-sink` fails when `has_alsa_ucm` is `True` but
no ALSA UCM sink device is found. `ce-oem-audio/alsa-ucm-detect-source` does
the same for source devices. Without these jobs, the plan would generate zero
sink or source tests and show no failure.

The template jobs use `flags: also-after-suspend`, so Checkbox can generate
after-suspend variants when the plan is used in a suspend flow.

The generated jobs use `user-interact-verify` because the final pass/fail
decision depends on human audio verification.

## Manifest

Enable the manifest gate before running the generated jobs:

```text
has_alsa_ucm: True
```

If this manifest value is not `True`, the generated ALSA UCM jobs are not
selected.

## Environment

### `ALSA_UCM_LOOPBACK_PAIRING`

Optional comma-separated Sink:Source pairs:

```text
ALSA_UCM_LOOPBACK_PAIRING=Speaker:Mic,Headphones:Headset
```

When set:

- sink-only resources exclude paired sinks
- source-only resources exclude paired sources
- loopback resources contain only configured pairs that exist for the verb

When unset:

- sink and source resources list all discovered devices of that type
- loopback resources emit no rows

### `ALSA_UCM_LOOPBACK_DURATION`

Optional loopback capture duration in seconds:

```text
ALSA_UCM_LOOPBACK_DURATION=10
```

If unset, the job command uses `10`.

## Resource input and output

Sink resources:

```bash
alsa_ucm_test.py resource sinks --pairing "$ALSA_UCM_LOOPBACK_PAIRING"
```

Source resources:

```bash
alsa_ucm_test.py resource sources --pairing "$ALSA_UCM_LOOPBACK_PAIRING"
```

Loopback resources:

```bash
alsa_ucm_test.py resource loopback --pairing "$ALSA_UCM_LOOPBACK_PAIRING"
```

Example sink output:

```text
SoundCard: sofsoundwire
SoundNumber: 0
Verbs: HiFi
SinksDevice: Speaker
SinksDeviceName: Speaker
```

Example source output:

```text
SoundCard: sofsoundwire
SoundNumber: 0
Verbs: HiFi
SourceDevice: Mic
SourceDeviceName: Digital Microphone
```

Example loopback output:

```text
SoundCard: sofsoundwire
SoundNumber: 0
Verbs: HiFi
SinksDevice: Speaker
SinksDeviceName: Speaker
SourceDevice: Mic
SourceDeviceName: Digital Microphone
```

## Test commands

Sink/source jobs run one generated resource row at a time. Sink jobs play a
test sound that the operator must hear. Source jobs record a WAV file and print
the file path so the operator can play or copy it for verification:

```bash
alsa_ucm_test.py test -c 0 -v HiFi -d Speaker
alsa_ucm_test.py test -c 0 -v HiFi -d Mic
```

Loopback jobs enable one sink and one source together. The helper records a WAV
file and prints the file path so the operator can play or copy it for
verification:

```bash
alsa_ucm_test.py loopback-test -c 0 -v HiFi \
    --sink-device Speaker \
    --source-device Mic \
    --duration 10
```

The helper saves and restores ALSA mixer state around each test. It uses the
ALSA tools of the system under test; see "Install the ALSA tools".
