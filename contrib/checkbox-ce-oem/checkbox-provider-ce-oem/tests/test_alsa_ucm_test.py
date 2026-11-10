import json
import subprocess
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

import alsa_ucm_test

# Part of the real "alsaucm -c 0 dump json" output of a Genio 520 EVK.
G520_DUMP = {
    "Verbs": {
        "HiFi": {
            "Comment": "Play high quality music",
            "Devices": {
                "Speaker": {
                    "Comment": "Lineout speaker",
                    "Values": {
                        "PlaybackChannels": "2",
                        "PlaybackPCM": "_ucm0001.hw:mt8391evk,0",
                    },
                },
                "Mic1": {
                    "Comment": "Analog microphone",
                    "Values": {
                        "CaptureChannels": "2",
                        "CapturePCM": "_ucm0001.hw:mt8391evk,4",
                    },
                },
            },
        }
    }
}
G520_CARDS = [{"index": 0, "short_name": "mt8391evk"}]


class FakeCardManager:
    def __init__(self):
        self.cards = [
            {
                "index": 0,
                "short_name": "sofsoundwire",
                "ucm_found": True,
            }
        ]

    def list_cards(self):
        return self.cards


class FakeParser:
    def run_alsaucm_dump(self, card_index):
        return {}

    def parse_alsaucm_json(self, dump):
        return {
            "HiFi": {
                "devices": [
                    {
                        "name": "Speaker",
                        "comment": "Speaker",
                        "type": alsa_ucm_test.UCM_TYPE_SINK,
                        "pcm": "hw:${CardId},0",
                        "channels": "4",
                    },
                    {
                        "name": "Headphones",
                        "comment": "Headphones",
                        "type": alsa_ucm_test.UCM_TYPE_SINK,
                        "pcm": "hw:${CardId},1",
                        "channels": "2",
                    },
                    {
                        "name": "Mic",
                        "comment": "Digital Microphone",
                        "type": alsa_ucm_test.UCM_TYPE_SOURCE,
                        "pcm": "hw:${CardId},2",
                        "channels": "2",
                    },
                    {
                        "name": "Headset",
                        "comment": "Headset Microphone",
                        "type": alsa_ucm_test.UCM_TYPE_SOURCE,
                        "pcm": "hw:${CardId},3",
                        "channels": "1",
                    },
                ]
            }
        }


class AlsaUcmTest(unittest.TestCase):
    """Unit tests for alsa_ucm_test.py."""

    def test_parse_pairing_spec(self):
        self.assertEqual(
            alsa_ucm_test.parse_pairing_spec("Speaker:Mic,Headphones:Headset"),
            [("Speaker", "Mic"), ("Headphones", "Headset")],
        )

    def test_build_sink_rows_filters_paired_sinks(self):
        rows = alsa_ucm_test.build_resource_rows(
            FakeCardManager(),
            FakeParser(),
            "sinks",
            "Speaker:Mic",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["SinksDevice"], "Headphones")
        self.assertNotIn("SourceDevice", rows[0])

    def test_build_source_rows_filters_paired_sources(self):
        rows = alsa_ucm_test.build_resource_rows(
            FakeCardManager(),
            FakeParser(),
            "sources",
            "Speaker:Mic",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["SourceDevice"], "Headset")
        self.assertNotIn("SinksDevice", rows[0])

    def test_build_loopback_rows(self):
        rows = alsa_ucm_test.build_resource_rows(
            FakeCardManager(),
            FakeParser(),
            "loopback",
            "Speaker:Mic",
        )

        self.assertEqual(
            rows,
            [
                {
                    "SoundCard": "sofsoundwire",
                    "SoundNumber": "0",
                    "Verbs": "HiFi",
                    "SinksDevice": "Speaker",
                    "SinksDeviceName": "Speaker",
                    "SourceDevice": "Mic",
                    "SourceDeviceName": "Digital Microphone",
                }
            ],
        )

    def test_print_resource_rows(self):
        output = StringIO()
        with mock.patch("sys.stdout", output):
            alsa_ucm_test.print_resource_rows(
                [
                    alsa_ucm_test.make_resource_row(
                        "sofsoundwire",
                        "0",
                        "HiFi",
                        sink=("Speaker", "Speaker"),
                    )
                ]
            )

        self.assertEqual(
            output.getvalue(),
            "SoundCard: sofsoundwire\n"
            "SoundNumber: 0\n"
            "Verbs: HiFi\n"
            "SinksDevice: Speaker\n"
            "SinksDeviceName: Speaker\n\n",
        )

    def test_cap_test_channels(self):
        self.assertEqual(alsa_ucm_test.cap_test_channels("4"), ("2", 2, 4))
        self.assertEqual(alsa_ucm_test.cap_test_channels("1"), ("1", 1, 1))
        self.assertEqual(alsa_ucm_test.cap_test_channels("0"), ("1", 1, 0))
        self.assertEqual(
            alsa_ucm_test.cap_test_channels("bad"), ("2", 2, None)
        )

    def test_alsa_ucm_command_format(self):
        self.assertEqual(
            alsa_ucm_test.AlsaUcmCli.argv(
                0,
                ("_verb", "HiFi"),
                ("_enadev", "Speaker"),
                ("_enadev", "Mic"),
            ),
            "alsaucm -c 0 set _verb HiFi set _enadev Speaker "
            "set _enadev Mic".split(),
        )

    def test_stream_command_builders(self):
        self.assertEqual(
            alsa_ucm_test.speaker_argv("hw:0,0", "2", "S16_LE"),
            [
                "speaker-test",
                "-D",
                "hw:0,0",
                "-c",
                "2",
                "-F",
                "S16_LE",
                "-r",
                "48000",
                "-t",
                "wav",
                "-l",
                "1",
            ],
        )
        self.assertEqual(
            alsa_ucm_test.arecord_argv(
                "hw:0,2", "2", "S16_LE", 10, "/tmp/test.wav"
            ),
            [
                "arecord",
                "-D",
                "hw:0,2",
                "-c",
                "2",
                "-f",
                "S16_LE",
                "-r",
                "48000",
                "-d",
                "10",
                "-t",
                "wav",
                "/tmp/test.wav",
            ],
        )

    @mock.patch("alsa_ucm_test.LoopbackRunner.run")
    def test_loopback_main_dispatch(self, mock_runner):
        mock_runner.return_value = 0

        result = alsa_ucm_test.main(
            [
                "loopback-test",
                "-c",
                "0",
                "-v",
                "HiFi",
                "--sink-device",
                "Speaker",
                "--source-device",
                "Mic",
                "--duration",
                "10",
            ]
        )

        self.assertEqual(result, 0)


class FakeRun:
    """Replace subprocess.run: record each argv, answer like the tools."""

    def __init__(self, fail=None, timeout=None, wav_bytes=0):
        self.calls = []
        self.fail = fail
        self.timeout = timeout
        self.wav_bytes = wav_bytes

    def __call__(self, argv, **kwargs):
        cmd = " ".join(argv)
        self.calls.append(cmd)
        if self.timeout and self.timeout in cmd:
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout"))
        if argv[0] == "arecord" and argv[-1].endswith(".wav"):
            Path(argv[-1]).write_bytes(bytes(self.wav_bytes))
        if cmd.endswith("dump json"):
            return subprocess.CompletedProcess(argv, 0, json.dumps(G520_DUMP))
        rc = 1 if self.fail and self.fail in cmd else 0
        return subprocess.CompletedProcess(argv, rc, "", "error" * rc)


@mock.patch.object(
    alsa_ucm_test.CardManager, "list_cards", return_value=G520_CARDS
)
class RunnerLifecycleTest(unittest.TestCase):
    """Run the test and loopback-test commands with fake ALSA tools."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmpdir = Path(tmp.name)
        patcher = mock.patch.object(tempfile, "tempdir", tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_main(self, fake, argv):
        with mock.patch("alsa_ucm_test.subprocess.run", fake), mock.patch(
            "sys.stdout", StringIO()
        ) as out, mock.patch("sys.stderr", StringIO()):
            rc = alsa_ucm_test.main(argv)
        return rc, out.getvalue()

    def assert_state_restored(self, fake):
        self.assertTrue(fake.calls[-1].startswith("alsactl -f"))
        self.assertTrue(fake.calls[-1].endswith("restore 0"))
        self.assertEqual(list(self.tmpdir.glob("*.state")), [])

    def test_sink_pass(self, _cards):
        fake = FakeRun()
        rc, out = self.run_main(
            fake, ["test", "-c", "0", "-v", "HiFi", "-d", "Speaker"]
        )
        self.assertEqual(rc, 0)
        self.assertIn("[PASS] Card 0 (mt8391evk) / HiFi / Speaker", out)
        self.assertIn(
            "alsaucm -c 0 set _verb HiFi set _enadev Speaker", fake.calls
        )
        self.assertIn(
            "speaker-test -D hw:0,0 -c 2 -F S16_LE -r 48000 -t wav -l 1",
            fake.calls,
        )
        self.assert_state_restored(fake)

    def test_source_records_wav(self, _cards):
        fake = FakeRun()
        rc, out = self.run_main(
            fake, ["test", "-c", "0", "-v", "HiFi", "-d", "Mic1"]
        )
        self.assertEqual(rc, 0)
        self.assertTrue(
            any(c.startswith("arecord -D hw:0,4 -c 2") for c in fake.calls)
        )
        self.assertIn("Recorded file saved to:", out)
        self.assert_state_restored(fake)

    def test_apply_failure_restores_state(self, _cards):
        fake = FakeRun(fail="_enadev Speaker")
        rc, out = self.run_main(
            fake, ["test", "-c", "0", "-v", "HiFi", "-d", "Speaker"]
        )
        self.assertEqual(rc, 1)
        self.assertIn("alsaucm apply exit code 1", out)
        self.assertFalse(any("speaker-test" in c for c in fake.calls))
        self.assert_state_restored(fake)

    def test_stream_failure_restores_state(self, _cards):
        fake = FakeRun(fail="speaker-test")
        rc, out = self.run_main(
            fake, ["test", "-c", "0", "-v", "HiFi", "-d", "Speaker"]
        )
        self.assertEqual(rc, 1)
        self.assertIn("stream test exit code 1", out)
        self.assert_state_restored(fake)

    def test_stream_timeout_restores_state(self, _cards):
        fake = FakeRun(timeout="speaker-test")
        with self.assertRaises(subprocess.TimeoutExpired):
            self.run_main(
                fake, ["test", "-c", "0", "-v", "HiFi", "-d", "Speaker"]
            )
        self.assert_state_restored(fake)

    def test_unknown_device_fails_before_apply(self, _cards):
        fake = FakeRun()
        rc, out = self.run_main(
            fake, ["test", "-c", "0", "-v", "HiFi", "-d", "Nope"]
        )
        self.assertEqual(rc, 1)
        self.assertIn(
            "device not found. Available devices: Mic1, Speaker", out
        )
        self.assertFalse(any(c.startswith("alsactl") for c in fake.calls))

    def loopback(self, fake):
        return self.run_main(
            fake,
            [
                "loopback-test",
                "-c",
                "0",
                "-v",
                "HiFi",
                "--sink-device",
                "Speaker",
                "--source-device",
                "Mic1",
                "--duration",
                "10",
            ],
        )

    def test_loopback_pass(self, _cards):
        # 10 s x 48000 Hz x 2 channels x 2 bytes / 100 = 19200 bytes minimum
        fake = FakeRun(wav_bytes=19200)
        rc, out = self.loopback(fake)
        self.assertEqual(rc, 0)
        self.assertIn("/ loopback / wav saved:", out)
        self.assert_state_restored(fake)

    def test_loopback_wav_too_small(self, _cards):
        fake = FakeRun(wav_bytes=19199)
        rc, out = self.loopback(fake)
        self.assertEqual(rc, 1)
        self.assertIn("recorded WAV too small (19199 bytes, min 19200)", out)
        self.assert_state_restored(fake)

    def test_loopback_capture_failure(self, _cards):
        fake = FakeRun(fail="arecord -D")
        rc, out = self.loopback(fake)
        self.assertEqual(rc, 1)
        self.assertIn("arecord exit code 1", out)
        self.assert_state_restored(fake)


class ParserExamplesTest(unittest.TestCase):
    """The docstring examples, with real G520 output."""

    def test_list_cards(self):
        text = (
            " 0 [mt8391evk      ]: mt8391-evk - mt8391-evk\n"
            "                      mediatek-Genio720520EVKP2V3eMMCBoot\n"
        )
        with mock.patch.object(
            Path, "exists", return_value=True
        ), mock.patch.object(Path, "read_text", return_value=text):
            cards = alsa_ucm_test.CardManager().list_cards()
        self.assertEqual(cards, G520_CARDS)

    def test_list_alsaucm_verbs(self):
        res = subprocess.CompletedProcess(
            [], 0, "  0: HiFi\n    Play high quality music\n"
        )
        with mock.patch("alsa_ucm_test.subprocess.run", return_value=res):
            verbs = alsa_ucm_test.CardManager().list_alsaucm_verbs(0)
        self.assertEqual(verbs, ["HiFi"])

    def test_resolve_pcm(self):
        self.assertEqual(
            alsa_ucm_test.resolve_pcm(
                "_ucm0001.hw:mt8391evk,0", 0, "mt8391evk"
            ),
            "hw:0,0",
        )
        self.assertEqual(
            alsa_ucm_test.resolve_pcm("hw:${CardId},2", 1), "hw:1,2"
        )


if __name__ == "__main__":
    unittest.main()
