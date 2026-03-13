#!/usr/bin/env python3
import subprocess
import signal
import os
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# --- Configuration ---
THERMALD_CMD = ["thermald", "--no-daemon", "--loglevel=debug", "--adaptive"]

# Patterns to search for (as bytes).
FAILURE_PATTERN = b"Also unable to evaluate any conditions"
SUCCESS_PATTERN = b"Start main loop"

# The grep command will search for either pattern, stop after the first match (-m 1),
# and flush its output immediately (--line-buffered).
GREP_CMD = [
    "grep",
    "--line-buffered",
    "-m",
    "1",
    "-e",
    FAILURE_PATTERN.decode("utf-8"),
    "-e",
    SUCCESS_PATTERN.decode("utf-8"),
]

TIMEOUT_SECONDS = 15


def stop_thermald_service():
    """
    Stop the thermald systemd service if it's running.
    Returns True if service was running and stopped, False if it wasn't running.
    """
    logging.info("--- Checking thermald systemd service ---")

    try:
        # Check if thermald service is active
        result = subprocess.run(
            ["systemctl", "is-active", "thermald"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0 and result.stdout.strip() == "active":
            logging.info("Thermald service is running. Stopping it...")
            stop_result = subprocess.run(
                ["systemctl", "stop", "thermald"],
                capture_output=True,
                text=True,
            )

            if stop_result.returncode == 0:
                logging.info("Thermald service stopped successfully.")
                return True
            else:
                logging.error(
                    f"Failed to stop thermald service: {stop_result.stderr}"
                )
                return False
        else:
            logging.info("Thermald service is not running.")
            return False

    except Exception as e:
        logging.error(f"Error checking/stopping thermald service: {e}")
        return False


def start_thermald_service():
    """
    Start the thermald systemd service.
    """
    logging.info("--- Restarting thermald systemd service ---")

    try:
        result = subprocess.run(
            ["systemctl", "start", "thermald"], capture_output=True, text=True
        )

        if result.returncode == 0:
            logging.info("Thermald service restarted successfully.")
        else:
            logging.error(
                f"Failed to restart thermald service: {result.stderr}"
            )

    except Exception as e:
        logging.error(f"Error restarting thermald service: {e}")


def run_thermald_grep_test():
    """
    Test thermald's adaptive engine startup by monitoring its output.

    This test launches thermald with adaptive engine and uses grep to detect
    which pattern appears first:
    - SUCCESS: "Start main loop" - adaptive engine started correctly
    - FAILURE: "Also unable to evaluate any conditions" - adaptive engine failed,
      thermald falls back to highest power profile

    The test captures the first occurrence of either pattern to determine if
    the adaptive engine initialization was successful.
    """
    logging.info("=== THERMALD ADAPTIVE ENGINE TEST ===")
    logging.info(
        "This test verifies that thermald's adaptive engine starts correctly."
    )
    logging.info(
        "Monitoring thermald output for adaptive engine initialization patterns..."
    )
    logging.info(f"Success pattern: '{SUCCESS_PATTERN.decode('utf-8')}'")
    logging.info(f"Failure pattern: '{FAILURE_PATTERN.decode('utf-8')}'")
    logging.info(f"Command: {' '.join(THERMALD_CMD)}")
    logging.info(f"Timeout: {TIMEOUT_SECONDS} seconds")
    logging.info("=" * 70)

    if os.geteuid() != 0:
        logging.error("\nERROR: This script requires sudo privileges.")
        logging.error("Please run it with: sudo python3 test_thermald.py")
        raise SystemExit(1)

    # Stop thermald service if it's running
    service_was_running = stop_thermald_service()

    thermald_proc = None
    grep_proc = None
    result_message = ""
    exit_code = 1  # Default to failure

    try:
        # 1. Start the thermald process.
        #    - Redirect stderr to stdout so grep sees all output.
        #    - preexec_fn=os.setsid creates a new process group for robust cleanup.
        thermald_proc = subprocess.Popen(
            THERMALD_CMD,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )
        logging.info(
            f"Started thermald with adaptive engine (PGID: {thermald_proc.pid})"
        )

        # 2. Start the grep process, piping thermald's output to its input.
        grep_proc = subprocess.Popen(
            GREP_CMD, stdin=thermald_proc.stdout, stdout=subprocess.PIPE
        )
        logging.info(f"Started pattern monitoring (grep PID: {grep_proc.pid})")
        logging.info("Waiting for adaptive engine initialization patterns...")

        # 3. Allow thermald's stdout pipe to be closed. This is VERY important.
        #    It prevents thermald from hanging if grep exits before thermald does.
        thermald_proc.stdout.close()

        # 4. Wait for grep to finish or for the timeout to expire.
        #    communicate() reads the output and waits for the process.
        try:
            grep_output, _ = grep_proc.communicate(timeout=TIMEOUT_SECONDS)

            # 5. Analyze grep's output to determine the result.
            if FAILURE_PATTERN in grep_output:
                result_message = (
                    "FAILURE: Thermald adaptive engine failed to initialize.\n"
                    "Found failure pattern first - thermald fell back to highest power profile."
                )
                exit_code = 1
            elif SUCCESS_PATTERN in grep_output:
                result_message = (
                    "SUCCESS: Thermald adaptive engine started correctly.\n"
                    "Found success pattern - adaptive engine is active."
                )
                exit_code = 0
            else:
                # This case means thermald exited before grep found anything.
                result_message = (
                    "FAILURE: Thermald process exited unexpectedly.\n"
                    "No adaptive engine patterns detected in output."
                )
                exit_code = 1

        except subprocess.TimeoutExpired:
            result_message = (
                f"FAILURE: Test timed out after {TIMEOUT_SECONDS} seconds.\n"
                "Thermald may be stuck or taking too long to initialize adaptive engine."
            )
            exit_code = 1

    except FileNotFoundError as e:
        logging.error(
            f"\nERROR: Command not found: '{e.filename}'. Is it installed?"
        )
        raise SystemExit(1)
    except Exception as e:
        result_message = (
            f"FAILURE: An unexpected error occurred during the test: {e}\n"
            "This may indicate system configuration issues."
        )
        exit_code = 1
    finally:
        # --- Graceful Cleanup ---
        logging.info("--- Cleaning up test processes ---")
        # First, ensure the grep process is gone
        if grep_proc and grep_proc.poll() is None:
            logging.info(
                f"Terminating leftover grep process {grep_proc.pid}..."
            )
            grep_proc.terminate()
            grep_proc.wait(timeout=2)
            if grep_proc.poll() is None:
                grep_proc.kill()

        # Then, clean up the main thermald process and its children
        if thermald_proc and thermald_proc.poll() is None:
            logging.info(
                f"Sending SIGTERM to thermald process group {thermald_proc.pid}..."
            )
            try:
                os.killpg(thermald_proc.pid, signal.SIGTERM)
                thermald_proc.wait(timeout=5)
                logging.info("Thermald process group terminated gracefully.")
            except ProcessLookupError:
                logging.info("Thermald process group already gone.")
            except subprocess.TimeoutExpired:
                logging.warning(
                    "Thermald did not respond to SIGTERM. Sending SIGKILL..."
                )
                os.killpg(thermald_proc.pid, signal.SIGKILL)
                logging.info("Thermald process group killed.")
        else:
            logging.info("Thermald process already terminated.")

        # Restart thermald service if it was originally running
        if service_was_running:
            start_thermald_service()

    logging.info("=" * 70)
    logging.info("=== THERMALD ADAPTIVE ENGINE TEST RESULT ===")
    logging.info(result_message)
    if exit_code == 0:
        logging.info("PASSED: Thermald adaptive engine is working correctly.")
    else:
        logging.info(
            "FAILED: Thermald adaptive engine did not start properly."
        )
    logging.info("=" * 70)
    return exit_code


def main():
    test_result = run_thermald_grep_test()
    raise SystemExit(test_result)


if __name__ == "__main__":
    main()
