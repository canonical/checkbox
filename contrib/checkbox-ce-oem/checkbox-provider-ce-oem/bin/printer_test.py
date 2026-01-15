#!/usr/bin/env python3
# This script rely on user input the brand name of the printer
# as the keyword to searching connected printer.
import argparse
import logging
import subprocess
import time
import re
from checkbox_support.helpers.timeout import run_with_timeout


def run_command(command: str):
    """Executes a shell command and returns the output."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logging.error("Error executing command: {}".format(e.stderr))
        return None


def find_printer_uri(keyword: str):
    """Scans lpinfo for a printer matching the keyword."""
    logging.info("--- Searching for printer matching: {} ---".format(keyword))
    output = run_command("lpinfo -v")
    if not output:
        return None

    # Look for the specific URI line
    for line in output.split("\n"):
        match = re.search(
            r"\S+://\S*{}\S*".format(re.escape(keyword)),
            line,
            re.IGNORECASE,
        )
        if match:
            return match.group(0)
    return None


def monitor_job(printer_name: str, job_id: str):
    """Checks the status of the job."""
    logging.info("--- Monitoring Job {} ---".format(job_id))

    while True:
        # Check if job is in the 'completed' list
        completed_jobs = run_command(
            "lpstat -W completed -o {}".format(printer_name)
        )
        if job_id in completed_jobs:
            logging.info(
                "SUCCESS: Job {} has been COMPLETED by the printer.".format(
                    job_id
                )
            )
            return

        # Check if it's still in the active queue
        active_jobs = run_command("lpq -P {}".format(printer_name))
        if job_id not in active_jobs and job_id in completed_jobs:
            logging.info("SUCCESS: Job {} finished.".format(job_id))
            return

        logging.info("Job pending/processing... checking again in 5s")
        time.sleep(5)


def teardown_printer(printer_name: str):
    """Removes the printer configuration."""
    logging.info("Removing printer '{}'...".format(printer_name))
    run_command("lpadmin -x {}".format(printer_name))


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    parser = argparse.ArgumentParser(description="Printer Test Script")
    parser.add_argument(
        "-k",
        "--keyword",
        required=True,
        type=str,
        help="Keyword to search for printer URI",
    )
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        help="Target model to link up",
    )
    parser.add_argument(
        "--check-device",
        action="store_true",
        help="Only check if the device is present the URI only",
    )
    args = parser.parse_args()
    keyword = args.keyword
    printer_name = "Printer_Tester"

    # 1. Find URI
    uri = find_printer_uri(keyword)
    if not uri:
        logging.error(
            "Could not find a printer with keyword '{}'.".format(keyword)
        )
        raise SystemExit(1)

    logging.info("Found URI: {}".format(uri))

    if args.check_device:
        return

    driver_opt = ""
    if args.model:
        driver_opt = "-m {}".format(args.model)
    elif "usb://" in uri:
        driver_opt = "-m raw"
    elif "ipp://" in uri:
        driver_opt = "-m everywhere"

    # 2. Create/Link the printer
    logging.info("Linking printer as '{}'...".format(printer_name))
    if (
        run_command(
            "lpadmin -p {} -v '{}' -E {}".format(printer_name, uri, driver_opt)
        )
        is None
    ):
        logging.error("Failed to link printer.")
        raise SystemExit(1)

    # 3. Print a test page
    logging.info("Sending test print job...")
    test_text = "Printer TEST\nSTATUS: LINKED\n"
    lp_output = run_command(
        "echo '{}' | lp -d {}".format(test_text, printer_name)
    )

    if lp_output and "request id is" in lp_output:
        # Extract Job ID (e.g., Printer test_Queue-10)
        job_id = lp_output.split(" ")[3]
        logging.info("Job submitted: {}".format(job_id))

        # 4. Monitor status
        try:
            run_with_timeout(monitor_job, 30, printer_name, job_id)
        except TimeoutError:
            logging.error(
                "TIMEOUT: Job did not reach 'completed' status within "
                "30 seconds."
            )
            teardown_printer(printer_name)
            raise SystemExit(1)
    else:
        logging.error("Failed to submit print job.")
        teardown_printer(printer_name)
        raise SystemExit(1)

    teardown_printer(printer_name)


if __name__ == "__main__":
    main()
