#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

target_package=${1:-ubuntu-desktop}

noninstalled=()
target_version="$(dpkg-query --showformat='${Version}' --show "$target_package")"
apt_show_ud="$(apt-cache show "${target_package}"="$target_version")"
recommends="$(echo "${apt_show_ud}"| grep ^Recommends | head -n 1)"
while read -r pkg; do
    # libreoffice-impress provides libreoffice-ogltrans, and libreoffice-ogltrans becomes a transitional package on Ubuntu 20.04.
    # shellcheck disable=SC2016
    if ! dpkg-query -W -f='${Status}\n' "$pkg" 2>&1 | grep "install ok installed" >/dev/null 2>&1 && [ "$pkg" != "libreoffice-ogltrans" ]; then
        noninstalled+=("$pkg")
    fi
done < <(echo "$recommends"| cut -d : -f 2-| xargs| sed 's/ //g'| tr , $'\n')

if [ -n "${noninstalled[*]}" ]; then
    IFS=' '
    echo "${noninstalled[*]} are not installed."
    exit 1
fi

echo "All packages in Recommends of ${target_package} are installed."
exit 0
