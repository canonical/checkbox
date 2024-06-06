#!/bin/bash

DIR=$(mktemp -d)
curl -L -o "$DIR"/CSME_Version_Detection_Tool_Linux.tar.gz "https://drive.google.com/uc?id=1u9wveOok5ZQcd_3-Z7KCPagTob2O57_R&export=download" > /dev/null 2>&1
RET=$?

if [ $RET -ne 0 ]; then
    echo "Intel CSME tool download failed, please download it manually from"
    echo "https://downloadcenter.intel.com/download/28632/Intel-Converged-Security-and-Management-Engine-Intel-CSME-Detection-Tool"
    exit 1
fi

tar xvf "$DIR"/CSME_Version_Detection_Tool_Linux.tar.gz -C "$DIR" > /dev/null 2>&1
RET=$?

if [ $RET -ne 0 ]; then
   echo "Can't extract the tool successfully"
   exit 1
fi

cd "$DIR" || exit
python3 intel_csme_version_detection_tool

rm -rf "$DIR"
