import json
import os
import subprocess
import sys
import time
from argparse import ArgumentParser, Namespace

import requests


def get_checkbox_revision(series: str, channel: str) -> str:
    """
    Get checkbox snap revision.
    """
    result = subprocess.run(
        ["snap", "info", f"checkbox{series}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        return None

    search_prefix = f"{channel}:"
    for line in result.stdout.splitlines():
        if line.strip().startswith(search_prefix):
            parts = line.split()
            revision = parts[3].strip("()")
            return revision

    return None


def start_sbom_request(series: str, revision: str) -> str:
    """
    Start a SBOM generation request for given revision.
    """
    url = "https://sbom-request.canonical.com/api/v1/artifacts/snap/store"
    payload = {
        "maintainer": "Canonical",
        "email": "ce-certification-qa@lists.canonical.com",
        "version": revision,
        "department": {"value": "devices_engineering", "type": "predefined"},
        "team": {"value": "certification", "type": "predefined"},
        "artifactName": f"checkbox{series}",
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    response_data = response.json()

    # Check if artifactId is present in the response
    if (
        "data" not in response_data
        or "artifactId" not in response_data["data"]
    ):
        raise ValueError("artifactId not found in response")

    artifact_id = response_data["data"]["artifactId"]
    print(f"Upload started successfully. Artifact ID: {artifact_id}")

    return artifact_id


def monitor_artifact_status(artifact_id, interval=10, timeout=3600) -> None:
    """
    Monitor the SBOM generation status.
    """
    status_url = f"https://sbom-request.canonical.com/api/v1/artifacts/status/{artifact_id}"
    headers = {"Accept": "application/json"}

    start_time = time.time()
    elapsed_time = 0

    print(f"Starting to monitor artifact status for ID: {artifact_id}")

    while elapsed_time < timeout:
        response = requests.get(status_url, headers=headers)

        if response.status_code != 200:
            print(
                f"Failed to get status. Status code: {response.status_code}, Response: {response.text}"
            )
            time.sleep(interval)
            elapsed_time = time.time() - start_time
            continue

        response_data = response.json()

        if (
            "data" not in response_data
            or "status" not in response_data["data"]
        ):
            print(f"Invalid response format: {response_data}")
            time.sleep(interval)
            elapsed_time = time.time() - start_time
            continue

        current_status = response_data["data"]["status"]
        print(
            f"Current status: {current_status} (Elapsed time: {elapsed_time:.1f}s)"
        )

        if current_status == "completed":
            print(
                f"Artifact processing completed after {elapsed_time:.1f} seconds"
            )
            return
        elif current_status == "failed":
            print(
                f"Artifact processing failed after {elapsed_time:.1f} seconds"
            )
            return

        time.sleep(interval)
        elapsed_time = time.time() - start_time

    raise TimeoutError(
        f"Timeout reached after {timeout} seconds. Artifact processing did not complete."
    )


def download_sbom(artifact_id, output_file=None):
    """
    Download the SBOM file and save it.
    """
    sbom_url = f"https://sbom-request.canonical.com/api/v1/artifacts/sbom/{artifact_id}"
    headers = {"Accept": "application/octet-stream"}

    print(f"Downloading SBOM for artifact ID: {artifact_id}")

    response = requests.get(sbom_url, headers=headers)
    response.raise_for_status()

    sbom_json = json.loads(response.text)
    if output_file:
        with open(output_file, "w") as f:
            json.dump(sbom_json, f, indent=4)
        print(f"SBOM saved to {output_file}")


def parse_arguments(argv: list[str] | None = None) -> Namespace:
    if argv is None:
        argv = sys.argv[1:]

    parser = ArgumentParser()
    parser.add_argument(
        "--series",
        help="Series of Checkbox snap (e.g. 20, 22, 24)",
        required=True,
    )
    parser.add_argument(
        "--channel",
        help="Channel of Checkbox snap (e.g. latest/stable)",
        required=True,
    )
    parser.add_argument(
        "--rev-output-path",
        help="The output file path for revision.",
        default=os.environ.get("GITHUB_OUTPUT"),
        required=False,
    )

    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_arguments()
    revision = get_checkbox_revision(args.series, args.channel)
    artifact_id = start_sbom_request(args.series, revision)
    monitor_artifact_status(artifact_id)
    download_sbom(
        artifact_id, f"/tmp/checkbox{args.series}-{revision}.sbom.json"
    )
    with open(args.rev_output_path, "a") as f:
        f.write(f"revision={revision}\n")
        f.write(f"series={args.series}\n")
