#!/bin/bash
set -e
MTDS=$(find /dev -regex '.*mtd[0-9][0-9]?' | awk -F "/" '{print $3}')
MTD_WRITEABLE_FLAG=0x400

listAllMtd() {
    for c in ${MTDS}; do
        echo "MTD_NAME: ${c}"
        echo ""
    done
}

countMtd() {
    count=$( listAllMtd | grep -c "MTD_NAME")
    if [ "${1}" == "$count" ]; then
        echo "The number of MTD is correct!"
    else
        echo "The number of MTD is incorrect!"
        exit 1 
    fi
}

# This function will get the size of MTD. (Unit: byte)
# size_hex is the MTD size convert to HEX, and it's for read and write the file to MTD.
# is_mtd_writable tells this MTD can be written or not (0 means read-only)
infoMtd() {
    info=$(mtd_debug info /dev/"$1")
    echo "##### MTD info #####"
    echo "$info"
    size=$(awk '/mtd.size/ {print $3}' <<< "$info")
    size_hex=$(printf '%x' "$size")
    mtd_flag=$(cat /sys/class/mtd/"$1"/flags)
    is_mtd_writable=$((MTD_WRITEABLE_FLAG & mtd_flag))
}

createTestFile() {
# $1 is the file path who will be used as random test file
# $2 is size of random test file (Unit: byte)
    echo "##### Create test file #####"
    dd if=/dev/urandom of="$1" bs=1 count="$2"
}

eraseMtd() {
# $1 is the specific mtd. e.g. mtd1
# $2 is size of random test file (Unit: byte)
    echo "##### Erase MTD #####"
    mtd_debug erase /dev/"$1" 0x0 0x"$2"
}

writeMtd() {
# $1 is the specific mtd. e.g. mtd1
# $2 is size of random test file. Should be the value of size_hex variable
# $3 is the path of source file
    echo "##### Write MTD #####"
    mtd_debug write /dev/"$1" 0x0 0x"$2" "$3"
}

readMtd() {
# $1 is the specific mtd. e.g. mtd1
# $2 is size of random test file. Should be the value of size_hex variable
# $3 is the path of destination file
    echo "##### Read MTD #####"
    mtd_debug read /dev/"$1" 0x0 0x"$2" "$3"
}

compareFile() {
# $1 is the path of compared file 1
# $2 is the path of compared file 2
# $3 is the specific mtd. e.g. mtd1
    echo "##### Compare File #####"
    if diff "$1" "$2"; then
        echo "$3 read and write files are consistent!"
    else
        echo "$3 read and write files are inconsistent!!"
        exit 1
    fi
}

main(){
# $1 is action in list/compare/count
# $2 is MTD device name. e.g. mtd0, mtd1 ...etc
    case ${1} in
        list) listAllMtd ;;
        compare)
            infoMtd "${2}"
            echo

            # Read-only
            if [[ $is_mtd_writable -eq "0" ]]; then
                echo "${2} is read-olny"
                readFile=$(mktemp)
                echo "1. Read content to $readFile"
                readMtd "${2}" "$size_hex" "$readFile"
            else
                echo "${2} is writable"
                originalContent=$(mktemp)
                echo "1. Backup the content to $originalContent"
                readMtd "${2}" "$size_hex" "$originalContent"

                echo "2. Perform read and write testing"
                readFile=$(mktemp)
                writeFile=$(mktemp)
                createTestFile "$writeFile" "$size"
                eraseMtd "${2}" "$size_hex"
                writeMtd "${2}" "$size_hex" "$writeFile"
                readMtd "${2}" "$size_hex" "$readFile"
                compareFile "$writeFile" "$readFile" "${2}"

                echo "3. Recover content"
                eraseMtd "${2}" "$size_hex"
                writeMtd "${2}" "$size_hex" "$originalContent"
            fi
            ;;
        count) countMtd "${2}";;
        *) echo "Need given parameter."
    esac
}

main "$@"
exit $?
