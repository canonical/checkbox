import unittest
from io import StringIO
from unittest import mock

import alsa_ucm_test


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
            alsa_ucm_test.AlsaUcmCli.fmt(
                "0",
                ("_verb", "HiFi"),
                ("_enadev", "Speaker"),
                ("_enadev", "Mic"),
            ),
            "alsaucm -c 0 set _verb HiFi set _enadev Speaker set _enadev Mic",
        )

    def test_stream_command_builders(self):
        self.assertEqual(
            alsa_ucm_test.StreamCommandBuilder.speaker_argv(
                "hw:0,0", "2", "S16_LE"
            ),
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
            alsa_ucm_test.StreamCommandBuilder.arecord_argv(
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

        result = alsa_ucm_test.main_from_args(
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


if __name__ == "__main__":
    unittest.main()
