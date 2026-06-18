#!/usr/bin/env python3

import os
from pathlib import Path
from contextlib import suppress


def iter_if_accessible(path: Path):
    with suppress(OSError):
        yield from path.iterdir()


def main():
    paths = {Path(x).resolve() for x in os.get_exec_path()}
    executables = set()
    for path in paths:
        all_files = filter(Path.is_file, iter_if_accessible(path))
        executables |= {
            f.name for f in all_files if os.access(str(f), os.X_OK)
        }
    for executable in sorted(list(executables), key=str.casefold):
        print("name:", executable)
        print()


if __name__ == "__main__":
    main()
