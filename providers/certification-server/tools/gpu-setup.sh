#!/bin/bash

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root"
   exit 1
fi

echo "Configuring system for GPU Testing"
echo "**********************************"
echo

# For now we need internet access for this to work.  Future versions will
# remove this necessity
[[ ! `ping -c 1 www.ubuntu.com` ]] \
    && echo "This script requires internet access to function correctly" \
    && exit 1

# Disable Nouveau and reset initramfs
if lsmod |grep -q nouveau; then
    echo "*  Disabling nouveau driver"
    echo blacklist nouveau > /etc/modprobe.d/blacklist-nvidia-nouveau.conf
    echo options nouveau modeset=0 >> /etc/modprobe.d/blacklist-nvidia-nouveau.conf
    echo "*  Updating initramfs"
    update-initramfs -u
    echo "*  Finished disabling nouveau driver"
else
    echo "*  nouveau not detected, proceeding..."
fi

echo "*"
echo "**********************************"

# Add required PPAs
echo "*  Adding Canonical graphis-drivers PPA" 
add-apt-repository -y ppa:graphics-drivers/ppa

echo "*  Adding nVidia package repository"

file_pattern="cuda-repo-ubuntu$(lsb_release -r | cut -f 2 | sed -es/\\.//)*.deb"
gw_ip=`ip route | awk '/default/ { print $3 }'`

# attempt a download from our MAAS server (presume the SUT's gw IP is MAAS)
wget -r -l1 -nd --no-parent -A "$file_pattern" http://$gw_ip/nvidia/
nvidia_pkg=`find / -name $file_pattern`

if [ -z "$nvidia_pkg" ]; then
    echo "*  No local package found, installing remote installer"
    wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64/cuda-repo-ubuntu1804_10.0.130-1_amd64.deb
    dpkg -i cuda-repo-ubuntu1804_10.0.130-1_amd64.deb
    apt-key adv --fetch-keys https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64/7fa2af80.pub
else
    echo "*  Local package detected at $nvidia_pkg... installing"
    key_cmd=`dpkg -i $nvidia_pkg |awk '/To install the key, run this command/{getline; print}'`
    $key_cmd
fi    

echo "*  Updating apt cache"
apt update

# Install necessary files
echo "*  Installing necessary pacakges"
apt install -y cuda nvidia-cuda-toolkit build-essential git


# get the gpu-burn repo and build it
echo "*  Cloning gpu-burn repo"
git clone https://github.com/wilicc/gpu-burn.git
cd gpu-burn
echo "*  Building gpu-burn"
make && echo "*  Build completed..."

echo "*  Completed installatiion. Please reboot the machine now"
echo "*  to load the nVidia proprietary drivers"
