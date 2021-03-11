config:
  raw.idmap: "both 1000 1000"
  environment.DISPLAY: :0
  user.user-data: |
    #cloud-config
    runcmd:
      - 'sed -i "s/; enable-shm = yes/enable-shm = no/g" /etc/pulse/client.conf'
      - "perl -i -p0e 's/(Unit.*?)\n\n/$1\nConditionVirtualization=!container\n\n/s' /lib/systemd/system/systemd-remount-fs.service"
      - 'echo export XAUTHORITY=/run/user/1000/gdm/Xauthority | tee --append /home/ubuntu/.profile'
    packages:
      - alsa-base
      - gir1.2-cheese-3.0
      - gir1.2-gst-plugins-base-1.0
      - gir1.2-gstreamer-1.0
      - gstreamer1.0-plugins-good
      - gstreamer1.0-pulseaudio
      - libgstreamer1.0-0
      - mesa-utils
      - pulseaudio
      - x11-apps
      - xvfb
    snap:
      commands:
        - systemctl start snapd.service
