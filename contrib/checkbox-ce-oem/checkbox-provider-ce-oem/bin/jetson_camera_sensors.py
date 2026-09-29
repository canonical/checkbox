#!/usr/bin/env python3
import subprocess


class CameraSensors:
    nvargus_lps_keys = [
        "entry_index",
        "source_index",
        "mode_index",
        "unique_name",
        "resolution",
        "frame_rate",
        "bitdepth_csi",
        "bitdepth_dyn",
        "mode_type",
    ]

    @staticmethod
    def run_nvargus_nvraw():
        result = subprocess.run(
            ["nvargus_nvraw", "--lps"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    def parse_table(self, nvargus_output):
        # skip version info and table header
        table = nvargus_output.splitlines()[4:]
        entries = [
            dict(zip(self.nvargus_lps_keys, filter(len, line.split("  "))))
            for line in table
        ]
        return entries

    def get_column(self, column_id, entries):
        if column_id not in self.nvargus_lps_keys:
            raise ValueError("Unknown column '{}'".format(column_id))

        return [row[column_id] for row in entries]


nvargus_output = CameraSensors.run_nvargus_nvraw()
parsed_table = CameraSensors().parse_table(nvargus_output)

sensor_ids = set(CameraSensors().get_column("source_index", parsed_table))
for sensor in sensor_ids:
    print("source_index: {}\n".format(sensor))
