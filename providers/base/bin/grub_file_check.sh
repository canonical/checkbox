#!/bin/bash

declare -A DICT_ARCH

DICT_ARCH=( [x86_64]='x86_64' [aarch64]='arm64' [armhf]='arm' )
FILE_CORE="/boot/grub/${DICT_ARCH[$(uname -m)]}-efi/core.efi"

if [ -e "${FILE_CORE}" ]; then
    echo "The file ${FILE_CORE} exists, shim and grub can be upgraded."
    exit 0
else
    echo "Due to the absence of the file ${FILE_CORE}, upgrading shim and grub becomes impossible."
    exit 1
fi