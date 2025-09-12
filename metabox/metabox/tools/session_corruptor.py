import gzip
import json

from pathlib import Path


def corrupt(path):
    with gzip.open(str(path), "rt") as f:
        session = json.load(f)
    session["session"]["desired_job_list"].append(
        "@ invalid id - intentionally corrupted session"
    )
    with gzip.open(str(path), "wt") as f:
        json.dump(session, f)


def main():
    for session in Path("/var/tmp/checkbox-ng/sessions").glob("*/session"):
        print("Corrupting session", str(session))
        corrupt(session)


if __name__ == "__main__":
    main()
