config:
  raw.idmap: "both 1000 1000"
  environment.DISPLAY: :0
  user.user-data: |
    #cloud-config
    runcmd:
      - 'sed -i "s/; enable-shm = yes/enable-shm = no/g" /etc/pulse/client.conf'
      - "perl -i -p0e 's/(Unit.*?)\n\n/$1\nConditionVirtualization=!container\n\n/s' /lib/systemd/system/systemd-remount-fs.service"
      - 'echo export XAUTHORITY=/run/user/1000/gdm/Xauthority | tee --append /home/ubuntu/.profile'
