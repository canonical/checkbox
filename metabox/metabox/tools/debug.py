import pylxd
from time import sleep
from metabox.core.lxd_execute import interactive_execute

from subprocess import CalledProcessError

cmd = "true"
while True:
    c = pylxd.Client()
    focal_c = c.containers.get("focal")
    ie = interactive_execute(focal_c, cmd, timeout=0.1)
    try:
        ie.check()
    except CalledProcessError:
        ...
    except TimeoutError:
        ...
    print(ie.result)
    if cmd == "true":
        assert ie.result == 0
        cmd = "false"
    elif cmd == "false":
        assert ie.result == 1
        cmd = "sleep 10"
    elif cmd == "sleep 10":
        assert ie.result == 137
        cmd = "true"
