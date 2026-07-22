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

snapcraft_file="$series/snap/snapcraft.yaml"
provider_commit_short_hash=$(git log -1 --format='%h' -- ../checkbox-provider-ce-oem)

if [ ! -f "$snapcraft_file" ]; then
	echo "$snapcraft_file not found"
	exit 1
fi

current_version=$(sed -n "s/^version:[[:space:]]*'\([^']*\)'/\1/p" "$snapcraft_file")
if [ -z "$current_version" ]; then
	echo "Could not read version from $snapcraft_file"
	exit 1
fi

if [[ "$current_version" == *-"$provider_commit_short_hash" ]]; then
	new_version="$current_version"
else
	new_version="${current_version}-${provider_commit_short_hash}"
fi

sed -i "s/^version:.*/version: '${new_version}'/" "$snapcraft_file"
echo "Updated $snapcraft_file version:"
grep '^version:' "$snapcraft_file"
