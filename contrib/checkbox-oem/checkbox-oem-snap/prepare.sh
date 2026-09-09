#!/usr/bin/env bash

clean=0
while getopts "c" opt; do
	case "$opt" in
	c) clean=1 ;;
	*)
		echo "usage: $0 [-c] SERIES"
		exit 1
		;;
	esac
done
shift $((OPTIND - 1))

series=$1

if [ -z "$series" ]; then
	echo "usage: $0 [-c] SERIES"
	echo
	echo "This tool populates snap's directory with missing files that are"
	echo "common between all series. The files in question may be found in"
	echo "the common_files directory"
	echo
	echo "  -c  clean the files this tool generates for SERIES instead of"
	echo "      generating them"
	exit 1
fi

if [ ! -d "$series" ]; then
	echo "$series not found"
	exit 1
fi

if [ "$clean" -eq 1 ]; then
	echo "Cleaning generated files from $series"
	rm -rf "$series/checkbox-provider-oem"
	rm -f "$series/version.txt"
	rm -f "$series"/*.snap
	exit 0
fi

echo "Copying over providers to $series"
rsync -r --links ../checkbox-provider-oem "$series/"

echo "Dumping version in version file for $series..."
version=$(sed -n 's/.*version="\([^"]*\)".*/\1/p' ../checkbox-provider-oem/manage.py)
if [ -z "$version" ]; then
	echo "Error: could not extract version from ../checkbox-provider-oem/manage.py"
	exit 1
fi
echo "$version" >"$series/version.txt"
