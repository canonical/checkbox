#!/bin/bash

if [[ $EUID -ne 0 ]]; then
   echo "ERROR: This script must be run as root"
   exit 1
fi

echo "Configuring system for GPU Testing"
echo "**********************************"
echo "*"

# For now we need internet access for this to work.  Future versions will
# remove this necessity
echo "*  Testing network connectivity"
[[ ! `ping -c 1 www.ubuntu.com` ]] \
    && echo "ERROR: This script requires internet access to function correctly" \
    && exit 1
echo "*"
echo "**********************************"
echo "*"
echo "*  Adding nVidia package repository"
## Leave the following bits for now, it's useful code to template if we sort
## out local hosting in the future.
#file_pattern="cuda-repo-ubuntu$(lsb_release -r | cut -f 2 | sed -es/\\.//)*.deb"
#gw_ip=`ip route | awk '/default/ { print $3 }'`

# attempt a download from our MAAS server (presume the SUT's gw IP is MAAS)
#wget -r -l1 -nd --no-parent -A "$file_pattern" http://$gw_ip/nvidia/
#nvidia_pkg=`find / -name $file_pattern`

#if [ -z "$nvidia_pkg" ]; then
#    echo "*  No local package found, installing remote installer"
#    wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64/cuda-repo-ubuntu1804_10.0.130-1_amd64.deb
#    dpkg -i cuda-repo-ubuntu1804_10.0.130-1_amd64.deb
#    apt-key adv --fetch-keys https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64/7fa2af80.pub
#else
#    echo "*  Local package detected at $nvidia_pkg... installing"
#    key_cmd=`dpkg -i $nvidia_pkg |awk '/To install the key, run this command/{getline; print}'`
#    $key_cmd
#fi    

## For now, require internet access and installing directly from nVidia
# SAUCE: https://developer.nvidia.com/cuda-downloads?target_os=Linux&target_arch=x86_64&target_distro=Ubuntu&target_version=1804&target_type=debnetwork

OSRELEASE=ubuntu`lsb_release -r | cut -f2 |sed -e 's/\.//'`

read -p "About to install $OSRELEASE [Y/n]: " foo

wget https://developer.download.nvidia.com/compute/cuda/repos/$OSRELEASE/x86_64/cuda-$OSRELEASE.pin
mv cuda-$OSRELEASE.pin /etc/apt/preferences.d/cuda-repository-pin-600
# Ran into a case where the 16.04 repo uses http while 18.04 uses https :/
KEYSERVER_URL_TAIL="://developer.download.nvidia.com/compute/cuda/repos/$OSRELEASE/x86_64/7fa2af80.pub"
SUCCESS=1
for KEYSERVER_URL_HEAD in https http; do
    KEYSERVER_URL=$KEYSERVER_URL_HEAD$KEYSERVER_URL_TAIL
    apt-key adv --fetch-keys $KEYSERVER_URL
    SUCCESS=$?
    [ $SUCCESS == 0 ] && break
done

add-apt-repository "deb http://developer.download.nvidia.com/compute/cuda/repos/$OSRELEASE/x86_64/ /"

# Install necessary files
apt update
echo "*  Installing necessary pacakges"
apt install -y build-essential git cuda

#fix the path to get nvcc from the cuda package
CUDA_PATH=$(find /usr/local -maxdepth 1 -type d -iname "cuda*")/bin
export PATH=$PATH:$CUDA_PATH

# get the gpu-burn repo and build it
echo "*  Cloning gpu-burn repo"
GPU_BURN_DIR=/opt/gpu-burn
git clone https://github.com/wilicc/gpu-burn.git $GPU_BURN_DIR
cd $GPU_BURN_DIR
echo "*  Building gpu-burn"
make && echo "*  Build completed..."
echo "*"
echo "*  Completed installatiion. Please reboot the machine now"
echo "*  to load the nVidia proprietary drivers"
