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

## Test plan

Run the plan directly (it is also nested in `ce-oem-manual`):

```text
ce-oem-audio-alsa-ucm-manual
```

This plan is not included in `ce-oem-audio-automated`. It includes these
template IDs:

```text
ce-oem-audio/alsa-ucm-sink-tests
ce-oem-audio/alsa-ucm-source-tests
ce-oem-audio/alsa-ucm-loopback-tests
```

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

If unset, the PXU command uses `10`.

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

The helper saves and restores ALSA mixer state around each test. It expects
the system under test to provide ALSA tools such as `alsaucm`, `speaker-test`,
`aplay`, `arecord`, and `alsactl`, usually from `alsa-utils`.

`strace` is optional. When available, the helper uses it to print stronger UCM
file diagnostics. When unavailable, the helper falls back to scanning standard
UCM paths and continues the test.
