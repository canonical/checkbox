#!/usr/bin/env python3
import os


def no_newlines(s: str):
    # newlines break resource output
    return s.replace("\n", "\\n")


def main():
    for key, value in os.environ.items():
        print("{}: {}".format(key, no_newlines(value)))


if __name__ == "__main__":
    main()
