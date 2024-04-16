#!/usr/bin/env python3
import sys
from optparse import OptionParser


def parse_buffer(input):
    output = [""]
    row = -1
    col = 0
    escape = ""
    saved = [0, 0]

    for ch in input:
        if ord(ch) == 27 or len(escape) > 0:
            # On ESC
            if chr(27) in [escape, ch]:
                escape = ""
                if ch == "c":
                    output = [""]
                    row = -1
                    col = 0
                    saved = [0, 0]
                elif ch == "D":
                    row += 1
                    if row == 0:
                        row = -1
                        output.append("")
                elif ch == "M":
                    row -= 1
                    if row < -len(output):
                        output = [""] + output
                elif ch == "7":
                    saved = [row + len(output), col]
                elif ch == "8":
                    [row, col] = saved
                    row -= len(output)
                elif ord(ch) in [27, 91]:
                    escape = ch
                continue
            # Just after hitting the extended ESC marker
            elif escape == "[":
                escape = ""

            if ch in "0123456789;":
                escape += ch
                continue
            elif ch in "Hf":
                opts = escape.split(";") + ["", ""]
                row = -len(output) + max(0, int("0" + opts[0]) - 1)
                col = max(0, int("0" + opts[1]) - 1)
            elif ch in "s":
                saved = [row + len(output), col]
            elif ch in "u":
                [row, col] = saved
                row -= len(output)
            elif ch in "K":
                if escape == "1":
                    output[row] = " " * (col + 1) + output[row][col + 1 :]
                elif escape == "2":
                    output[row] = ""
                else:
                    output[row] = output[row][:col]
            elif ch in "J":
                if len(escape) == 0:
                    output = output[:row] + [""]
                else:
                    for i in range(row + len(output) + 1):
                        output[i] = ""
            elif ch in "A":
                row -= max(1, int("0" + escape.split(";")[0]))
                if row <= len(output):
                    row = -len(output)
            elif ch in "B":
                row += max(1, int("0" + escape.split(";")[0]))
                while row >= 0:
                    output.append("")
                    row -= 1
            elif ch in "C":
                col += max(1, int("0" + escape.split(";")[0]))
            elif ch in "D":
                col = max(0, col - max(1, int("0" + escape.split(";")[0])))

            escape = ""
            continue

        # Control char
        if ch in "\r\n\f\t\b":
            if ch == "\r":
                col = 0
            if ch in "\n\f":
                row += 1
                if row == 0:
                    row = -1
                    output.append("")
                col = 0
            if ch == "\t":
                col = (col + 8) & ~7
            if ch == "\b":
                col = max(0, col - 1)
            continue

        # Keep to ascii
        if ord(ch) not in range(32, 127):
            ch = "?"
        if len(output[row]) < col:
            output[row] += " " * (col - len(output[row]))
        output[row] = output[row][:col] + ch + output[row][col + 1 :]
        col += 1

    return "\n".join(output)


def parse_file(file):
    output = file.read()
    return parse_buffer(output)


def parse_filename(filename):
    file = open(filename)
    try:
        output = parse_file(file)
    finally:
        file.close()

    return output


def main(args):
    usage = "Usage: %prog [OPTIONS] [FILE...]"
    parser = OptionParser(usage=usage)
    parser.add_option(
        "-o",
        "--output",
        metavar="FILE",
        help="File where to output the result.",
    )
    (options, args) = parser.parse_args(args)

    # Write to stdout
    if not options.output or options.output == "-":
        output = sys.stdout

    # Or from given option
    else:
        output = open(options.output, "w")

    # Read from sdin
    if not args or (len(args) == 1 and args[0] == "-"):
        output.write(parse_file(sys.stdin))

    # Or from filenames given as arguments
    else:
        for arg in args:
            output.write(parse_filename(arg))

    if options.output and options.output != "-":
        output.close()

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
