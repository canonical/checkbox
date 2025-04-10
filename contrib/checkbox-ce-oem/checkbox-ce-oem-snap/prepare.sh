#!/usr/bin/env bash

series=$1

if [ -z "$series" ]; then
	echo "usage: $0 SERIES"
	echo
	echo "This tool populates snap's directory with missing files that are"
	echo "common between all series. The files in question may be found in"
	echo "the common_files directory"
	exit 1
fi

if [ ! -d "$series" ]; then
	echo "$series not found"
	exit 1
fi

echo "Copying over providers to $series"
rsync -r --links ../checkbox-provider-ce-oem "$series/"
