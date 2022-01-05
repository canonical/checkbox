#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

noninstalled=()
while read -r pkg; do
    # libreoffice-impress provides libreoffice-ogltrans, and libreoffice-ogltrans becomes a transitional package on Ubuntu 20.04.
    # shellcheck disable=SC2016
    if ! dpkg-query -W -f='${Status}\n' "$pkg" 2>&1 | grep "install ok installed" >/dev/null 2>&1 && [ "$pkg" != "libreoffice-ogltrans" ]; then
        noninstalled+=("$pkg")
    fi
done < <(apt-cache show ubuntu-desktop | grep ^Recommends | head -n 1 | cut -d : -f 2- | xargs | sed 's/ //g' | tr , $'\n')

if [ -n "${noninstalled[*]}" ]; then
    IFS=' '
    echo "${noninstalled[*]} are not installed."
    exit 1
fi

echo "All packages in Recommends of ubuntu-desktop are installed."
exit 0
