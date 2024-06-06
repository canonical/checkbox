#!/bin/bash

if [ -z "$1" ]; then
  echo "usage: $0 {output} [dpkg.list]"
  exit 0
fi

ADDITIONAL_OPTIONS=""
if [ -n "$2" ]; then
    ADDITIONAL_OPTIONS="--include-packages $2"
fi

mkdir -p "$1" && cd "$1" || exit 1

# See also: https://ubuntu.com/security/oval

RELEASE=$(lsb_release -cs)
OVAL_XML=com.ubuntu.$RELEASE.usn.oval.xml
OVAL_XML_BZ2=$OVAL_XML.bz2
REPORT_HTML=report.html

# 1. Download the compressed XML
wget "https://security-metadata.canonical.com/oval/$OVAL_XML_BZ2" &>/dev/null

# 2. Extract the OVAL XML
bunzip2 "$OVAL_XML_BZ2"

# 3. Generate the report HTML
oscap oval eval --report "$REPORT_HTML" "$OVAL_XML" &>/dev/null

oval-report.py --version

# shellcheck disable=SC2086
oval-report.py --report "$REPORT_HTML" --release "$RELEASE" $ADDITIONAL_OPTIONS
