#!/bin/bash
# shellcheck disable=SC2317
#refer to https://web.archive.org/web/20230614200306/https://01.org/blogs/qwang59/2020/linux-s0ix-troubleshooting
set -e
state="pass"
command -v turbostat || exit 1
session_folder="$PLAINBOX_SESSION_SHARE"

declare -A stats_p=( [gfxrc6]=0 [pkg_pc10]=7 [s0ix]=8 )
declare -A turbostat=( [gfxrc6]=0 [pkg_pc10]=0 [s0ix]=0 )
declare -A avg_criteria=( [gfxrc6]=50 [pkg_pc10]=80 [s0ix]=70 )

usage() {
cat << EOF
usage: $0 options
    this tool will run turbostat and check if the power state meet our requirement.
    most of operations are need root permission.

    -h|--help print this message
    --s2i     get into s2i before run turbostat
    --folder  sepcify the path of folder that you want to store temp logs. The default one is $session_folder
    -f        read external turbostat log instead of doing turbostat.; do not need root permission.
              please get log by this command:
              \$turbostat --out your-log --show GFX%rc6,Pkg%pc2,Pkg%pc3,Pkg%pc6,Pkg%pc7,Pkg%pc8,Pkg%pc9,Pk%pc10,SYS%LPI
              then:
              \$$0 -f path-to-your-log
EOF
exit 1
}

while [ $# -gt 0 ]
do
    case "$1" in
        -h | --help)
            usage 0
            exit 0
            ;;
        --s2i)
            S2I=1;
            ;;
        --folder)
            shift
            [ -d "$i" ] || usage
            session_folder=$1;
            ;;
        -f)
            shift
            if [ -f "$1" ]; then
                EX_FILE="$1";
            fi
            ;;
        *)
        usage
       esac
       shift
done

STAT_FILE="$session_folder/s2i-turbostat.log"

if_root(){
   if [ "$(id -u)" != "0" ]; then
       >&2 echo "[ERROR]need root permission"
       usage
   fi
}
if [ "$S2I" == "1" ]; then
    if_root
    echo "[INFO] getting turbostat log. Please wait for 60s"
    turbostat --out "$STAT_FILE" --show GFX%rc6,Pkg%pc2,Pkg%pc3,Pkg%pc6,Pkg%pc7,Pkg%pc8,Pkg%pc9,Pk%pc10,SYS%LPI rtcwake -m freeze -s 60
elif [ -n "$EX_FILE" ]; then
    cp "$EX_FILE" "$STAT_FILE"
else
    if_root
    echo "[INFO] getting turbostat log. Please wait for about 240s"
    turbostat --num_iterations 60 --out "$STAT_FILE" --show GFX%rc6,Pkg%pc2,Pkg%pc3,Pkg%pc6,Pkg%pc7,Pkg%pc8,Pkg%pc9,Pk%pc10,SYS%LPI
fi
while read -r -a line; do
    c=$((c+1));
    for i in "${!turbostat[@]}"; do
        turbostat[$i]=$(bc <<< "${turbostat[$i]}+${line[${stats_p[$i]}]}");
    done
done < <(grep -v "[a-zA-Z]" "$STAT_FILE")

for i in "${!turbostat[@]}"; do
    turbostat[$i]=$(bc <<< "${turbostat[$i]}/$c");
    echo "[INFO] checking $i : ${turbostat[$i]}%"
    if [ "$(bc <<< "${turbostat[$i]} > ${avg_criteria[$i]}")" == "1" ]; then
        echo "Passed."
    else
        >&2 echo "Failed" "avg $i : ${turbostat[$i]} NOT > ${avg_criteria[$i]} "
        state="failed"
    fi
done

if [ "$state" != "pass" ]; then
    echo "Your system not get Intel CPU PC10 or s0ix as expected, it could impact e-star compliance."
    echo "If the following test cases not run, that means your CPU architure or kernel driver not support PC10 or s0ix, please open bugs for HWE"
    echo " - power-management/cpu-low-power-idle"
    echo " - power-management/system-low-power-idle executed and passed."
    echo "Otherwise, please get PHM report to check which device blocking PC10 or s0ix and open bugs for HWE to check kernel modules"
    echo ""
    echo "reference:"
    echo " - https://web.archive.org/web/20230614200306/https://01.org/blogs/qwang59/2020/linux-s0ix-troubleshooting"
    echo " - https://blog.csdn.net/yuzaipiaofei/article/details/90384456"
    exit 1
fi
