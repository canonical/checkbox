#!/bin/bash
set -e
MTDS=$(ls /dev/mtd[0-9] | awk -F "/" '{print $3}')

listAllMtd() {
    for c in ${MTDS}; do
        echo "MTD_NAME: ${c}"
        echo ""
    done
}

countMtd() {
    count=$( listAllMtd | grep "MTD_NAME" | wc -l)
    if [ "${1}" == "$count" ]; then
        echo "The number of MTD is correct!"
    else
        echo "The number of MTD is incorrect!"
        exit 1 
    fi
}

# This function will get the size of MTD.
# size_hex is the MTD size convert to HEX, and it's for read and write the file to MTD.
# size=$(awk '/mtd.size/ {print $3}' <<< "$info")
# size_hex=$(printf '%x' "$size")
infoMtd() {
    info=$(mtd_debug info /dev/"$1")
    echo "##### MTD info #####"
    echo "$info"
    size=$(awk '/mtd.size/ {print $3}' <<< "$info")
    size_hex=$(printf '%x' "$size")
}

createTestFile() {
    echo "##### Create test file #####"
    dd if=/dev/urandom of="$writeFile" bs=1 count="$1"
}

eraseMtd() {
    echo "##### Erase MTD #####"
    mtd_debug erase /dev/"$1" 0x0 0x"$2"
}

writeMtd() {
    echo "##### Write MTD #####"
    mtd_debug write /dev/"$1" 0x0 0x"$2" "$writeFile"
}

readMtd() {
    echo "##### Read MTD #####"
    mtd_debug read /dev/"$1" 0x0 0x"$2" "$readFile"
}

compareFile() {
    echo "##### Compare File #####"
    diff "$writeFile" "$readFile" && echo "$1 read and write file are consistency!" || (echo "$1 read and write file are inconsistency!!" ; exit 1)
}

main(){
# $1 is action in list/compare/count
# $2 is MTD device name. e.g. mtd0, mtd1 ...etc
    case ${1} in
        list) listAllMtd ;;
        compare) 
            writeFile=$(mktemp)
            readFile=$(mktemp)
            infoMtd "${2}"
            createTestFile "$size"
            eraseMtd "${2}" "$size_hex"
            writeMtd "${2}" "$size_hex"
            readMtd "${2}" "$size_hex"
            compareFile "${2}" ;;
        count) countMtd "${2}";;
        *) echo "Need given parameter."
    esac
}

main "$@"
exit $?