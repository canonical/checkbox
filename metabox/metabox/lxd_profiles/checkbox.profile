config:
  raw.idmap: "both 1000 1000"
  environment.DISPLAY: :0
  user.user-data: |
    #cloud-config
    runcmd:
      - 'sed -i "s/; enable-shm = yes/enable-shm = no/g" /etc/pulse/client.conf'
      - "perl -i -p0e 's/(Unit.*?)\n\n/$1\nConditionVirtualization=!container\n\n/s' /lib/systemd/system/systemd-remount-fs.service"
      - 'echo export XAUTHORITY=/run/user/1000/gdm/Xauthority | tee --append /home/ubuntu/.profile'
    apt:
      sources:
        stable_ppa:
          source: "ppa:hardware-certification/public"
    packages:
      - alsa-base
      - jq
      - python3-jinja2
      - python3-markupsafe
      - python3-packaging
      - python3-padme
      - python3-pip
      - python3-psutil
      - python3-pyparsing
      - python3-requests-oauthlib
      - python3-tqdm
      - python3-urwid
      - python3-xlsxwriter
      - virtualenv
