#!/bin/bash

result=0

sources_list=$1
repositories=$2

if [ -z "$sources_list" ]; then
    echo "Must provide sources list location, e.g. /etc/apt/sources.list"
    exit 1
fi

if [ -z "$repositories" ]; then
    echo "Must provide list of repositories to check for, e.g. 'deb http://gb.archive.ubuntu.com/ubuntu/ precise multiverse, deb http://gb.archive.ubuntu.com/ubuntu/ precise-updates multiverse'"
    exit 1
fi

IFS=$','
for repository in $repositories; do
    if grep -q "$repository" "$sources_list"; then
        echo "$repository found in $sources_list"
    else
        echo "$repository not found in $sources_list"
        result=1
    fi
done

exit $result
