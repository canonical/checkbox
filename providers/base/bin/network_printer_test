#!/bin/bash

usage() {
    cat <<EOU

${0} - add a network printer and send a test page

 Usage: ${0} [ -p <printer> ] [ -s <server> ]

    -p <printer> -- specify a printer to use, by name
    -s <server>  -- specify a network server to use

 Note: this script expects printers over the IPP protocol only.

EOU
}

while [ $# -gt 0 ]
do
    case "$1" in
        -p)
            if echo ${2} | grep -q -c '^-'; then
                usage
                exit 1
            fi
            printer=${2}
            shift
            ;;
        -s)
            if echo ${2} | grep -q -c '^-'; then
                usage
                exit 1
            fi
            server=${2}
            shift
            ;;
        --usage)
            usage
            exit 1
            ;;
    esac
    shift
done

if [ -z $server ]; then
    echo "Nothing to do with no server defined. (See $0 --usage)"
    exit 0
fi

printer=${printer:-PDF}

lpadmin -E -v ipp://${server}/printers/${printer}
cupsenable ${printer}
cupsaccept ${printer}

lsb_release -a | lp -t "lsb_release" -d ${printer}

