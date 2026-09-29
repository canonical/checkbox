#!/bin/bash

# Execute a resource command and keep resource jobs non-fatal.
# - Print stdout only when the wrapped command succeeds.
# - Suppress stderr.
# - Always exit 0.

if [ "$#" -eq 0 ]; then
	exit 0
fi

# Optional separator for readability in callers:
# resource_wrapper.sh -- <cmd> <arg1> <arg2> ...
if [ "$1" = "--" ]; then
	shift
fi

if [ "$#" -eq 0 ]; then
	exit 0
fi

# Keep every original argument exactly as passed.
cmd=("$@")

if output=$("${cmd[@]}" 2>/dev/null); then
	if [ -n "$output" ]; then
		printf '%s\n' "$output"
	fi
fi

exit 0