#!/usr/bin/env python3

"""
Script to test Intel TDX

Copyright (C) 2013, 2014 Canonical Ltd.

Authors
  Hector Cao <hector.cao@canonical.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""

import argparse
import enum
import os
import pathlib
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request

import cpuinfo


def tcp_port_available():
    sock = socket.socket()
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class QemuEfiMachine(enum.Enum):
    OVMF_Q35 = 1
    OVMF_Q35_TDX = 2


class QemuEfiVariant(enum.Enum):
    MS = 1
    SECBOOT = 2
    SNAKEOIL = 3


class QemuEfiFlashSize(enum.Enum):
    DEFAULT = 1
    SIZE_4MB = 2


class QemuAccel:
    def __init__(self):
        self.accel = 'kvm'

    def args(self):
        return ['-accel', self.accel]


class QemuCpu:
    def __init__(self):
        self.cpu_type = 'host'
        self.cpu_flags = ''
        self.nb_cores = 16
        self.nb_sockets = 1

    def args(self):
        smp = ['-smp', f'{self.nb_cores},sockets={self.nb_sockets}']
        if self.cpu_flags != '':
            cpu = ['-cpu', self.cpu_type + self.cpu_flags]
        else:
            cpu = ['-cpu', self.cpu_type]
        return cpu + smp


class QemuGraphic():
    def __init__(self):
        self.nographic = True

    def args(self):
        if self.nographic:
            return ['-nographic']
        return []


class QemuSerial():
    def __init__(self, serial_file : str = None):
        self.serial_file = serial_file

    def args(self):
        if self.serial_file:
            return [
                '-chardev', f'file,id=c1,path={self.serial_file},signal=off',
                '-device', 'isa-serial,chardev=c1'
            ]
        return ['-serial', 'stdio']


class QemuUserConfig:
    def __init__(self):
        self.nodefaults = True
        self.user_config = False

    def args(self):
        _args = []
        if self.nodefaults:
            _args.extend(['-nodefaults'])
        if not self.user_config:
            _args.extend(['-no-user-config'])
        return _args


class QemuMemory:
    def __init__(self, memory='2G'):
        self.memory = memory

    def args(self):
        return ['-m', self.memory]


class QemuOvmf():
    def __init__(self, machine):
        # cannot use pflash with kvm accel, need kvm support
        # so use bios by default
        self.bios = True
        self.bios_path = '/usr/share/ovmf/OVMF.fd'
        self.ovmf_code_path = None
        self.ovmf_vars_template_path = None
        self.flash_size = QemuEfiFlashSize.SIZE_4MB
        self.variant = None
        self.machine = machine

    def _get_default_flash_paths(self, machine, variant, flash_size):
        assert (machine in QemuEfiMachine)
        assert (variant is None or variant in QemuEfiVariant)
        assert (flash_size in QemuEfiFlashSize)

        # Remaining possibilities are OVMF variants
        assert (
            flash_size in [
                QemuEfiFlashSize.DEFAULT, QemuEfiFlashSize.SIZE_4MB
            ]
        )
        size_ext = '_4M'
        OVMF_ARCH = "OVMF"
        return (
            f'/usr/share/OVMF/{OVMF_ARCH}_CODE{size_ext}.ms.fd',
            f'/usr/share/OVMF/{OVMF_ARCH}_VARS{size_ext}.fd'
        )

    def args(self):
        _args = []
        if self.bios:
            _args = ['-bios', self.bios_path]
        else:
            if not self.ovmf_code_path:
                (self.ovmf_code_path, self.ovmf_vars_template_path) = self._get_default_flash_paths(  # noqa: E501
                    self.machine, self.variant, self.flash_size)
            pflash = self.PflashParams(self.ovmf_code_path, self.ovmf_vars_template_path)  # noqa: E501
            _args = pflash.params
        return _args

    class PflashParams:
        '''
        Used to generate the appropriate -pflash arguments for QEMU. Mostly
        used as a fancy way to generate a per-instance vars file and have it
        be automatically cleaned up when the object is destroyed.
        '''
        def __init__(self, ovmf_code_path, ovmf_vars_template_path):
            self.params = [
                '-drive',
                'file=%s,if=pflash,format=raw,unit=0,readonly=on' %
                (ovmf_code_path),
            ]
            if ovmf_vars_template_path is None:
                self.varfile_path = None
                return
            with tempfile.NamedTemporaryFile(delete=False) as varfile:
                self.varfile_path = varfile.name
                with open(ovmf_vars_template_path, 'rb') as template:
                    shutil.copyfileobj(template, varfile)
                    self.params = self.params + [
                        '-drive',
                        'file=%s,if=pflash,format=raw,unit=1,readonly=off' %
                        (varfile.name)
                    ]

        def __del__(self):
            if self.varfile_path is None:
                return
            os.unlink(self.varfile_path)


class QemuMachineType:
    Qemu_Machine_Params = {
        QemuEfiMachine.OVMF_Q35: ['-machine', 'q35,kernel_irqchip=split'],
        QemuEfiMachine.OVMF_Q35_TDX: [
            '-machine', 'q35,kernel_irqchip=split,confidential-guest-support=tdx']  # noqa: E501
    }

    def __init__(self, machine=QemuEfiMachine.OVMF_Q35_TDX):
        self.machine = machine
        self.qgs_addr = None

    def enable_qgs_addr(self, addr : dict = {'type': 'vsock', 'cid': '2', 'port': '4050'}):  # noqa: E501
        """
        Enable the QGS (Quote Generation Service) address
        The address is a dictionary that corresponds to the object
        (https://qemu-project.gitlab.io/qemu/interop/qemu-qmp-ref.html#qapidoc-77)
        By default, the address is a vsock address with cid=2 (host cid)
        and port=4050
        """
        self.qgs_addr = addr

    def args(self):
        qemu_args = self.Qemu_Machine_Params[self.machine]
        if self.machine == QemuEfiMachine.OVMF_Q35_TDX:
            tdx_object = {'qom-type': 'tdx-guest', 'id': 'tdx'}
            if self.qgs_addr:
                tdx_object.update({'quote-generation-socket': self.qgs_addr})
            qemu_args = ['-object', str(tdx_object)] + qemu_args
        return qemu_args


class QemuBootType:
    def __init__(self,
                 image_path=None,
                 kernel=None,
                 initrd=None,
                 append=None):
        self.image_path = image_path
        self.kernel = kernel
        self.initrd = initrd
        self.append = append

    def args(self):
        _args = []
        if self.kernel:
            _args.extend(['-kernel', self.kernel])
            if self.append:
                _args.extend(['-append', f'{self.append}'])
            else:
                _args.extend(['-append', 'root=/dev/vda1 console=ttyS0'])
        if self.initrd:
            _args.extend(['-initrd', self.initrd])
        _args.extend([
            '-drive', f'file={self.image_path},if=none,id=virtio-disk0',
            '-device', 'virtio-blk-pci,drive=virtio-disk0'])
        return _args


class QemuCommand:

    def __init__(
            self,
            workdir,
            machine,
            memory='2G',
            variant=None,
    ):
        self.workdir = workdir
        self.plugins = {'cpu': QemuCpu(),
                        'accel': QemuAccel(),
                        'graphic': QemuGraphic(),
                        'config': QemuUserConfig(),
                        'memory': QemuMemory(memory),
                        'ovmf' : QemuOvmf(machine),
                        'serial' : QemuSerial(f'{self.workdir}/serial.log'),
                        'machine' : QemuMachineType(machine)}
        self.command = ['-pidfile', f'{self.workdir}/qemu.pid']

    def get_command(self):
        _args = ['qemu-system-x86_64']
        for p in self.plugins.values():
            _args.extend(p.args())
        return _args + self.command

    def add_qemu_run_log(self):
        # serial to file
        self.command = self.command + [
            '-D', f'{self.workdir}/qemu-log.txt'
        ]

    def add_port_forward(self, fwd_port):
        self.command = self.command + [
            '-device', 'virtio-net-pci,netdev=nic0_td',
            '-netdev', f'user,id=nic0_td,hostfwd=tcp::{fwd_port}-:22'
        ]

    def add_image(self, image_path):
        self.plugins['boot'] = QemuBootType(image_path=image_path)

    def add_qmp(self):
        try:
            if self.qmp_file is not None:
                return self.qmp_file
        except AttributeError:
            pass
        self.qmp_file = f'{self.workdir}/qmp.sock'
        self.command = self.command + [
            '-qmp', f'unix:{self.qmp_file},server=on,wait=off',
        ]

    def add_vsock(self, guest_cid):
        self.command = self.command + [
            '-device', 'vhost-vsock-pci,guest-cid=%d' % (guest_cid),
        ]

    def add_monitor(self):
        try:
            if self.monitor_file is not None:
                return self.monitor_file
        except AttributeError:
            pass
        self.monitor_file = f'{self.workdir}/monitor.sock'
        self.command = self.command + [
            '-monitor', 'unix:%s,server,nowait' % (self.monitor_file)
        ]
        return self.monitor_file


class QemuMonitor():
    DELIMITER_STRING = '(qemu)'
    READ_TIMEOUT = 2
    CONNECT_RETRIES = 60

    def __new__(cls, qemu):
        # only 1 monitor per qemu machine
        if qemu.monitor is None:
            qemu.monitor = super().__new__(cls)
        return qemu.monitor

    def __init__(self, qemu):
        self.socket = None
        assert qemu.qcmd.monitor_file is not None, "Monitor socket file is undefined"  # noqa: E501
        self.socket = socket.socket(socket.AF_UNIX,
                                    socket.SOCK_STREAM)
        for _ in range(self.CONNECT_RETRIES):
            try:
                print(f'Try to connect to qemu : {qemu.qcmd.monitor_file}')
                self.socket.connect(qemu.qcmd.monitor_file)
                # connection ok -> exit
                break
            except Exception as e:
                print(f'Exception {e}')
                # give some time to make sure socket file is available
                time.sleep(1)
        self.socket.settimeout(self.READ_TIMEOUT)
        # wait for prompt
        print(f'Connected : {qemu.qcmd.monitor_file}, wait for prompt.')
        self.wait_prompt()

    def recv_data(self):
        msg = ''
        try:
            while True:
                recv_data = self.socket.recv(1024)
                # empty data is returned -> connection closed by remote peer
                if len(recv_data) == 0:
                    break
                msg += recv_data.decode('utf-8')
        except Exception as e:
            print(f'Exception {e}')
        return msg

    def wait_prompt(self):
        msg = self.recv_data()
        assert self.DELIMITER_STRING in msg, f'Fail on wait for monitor prompt : {msg}'  # noqa: E501

    def recv(self):
        """
        Return an array of messages from qemu process
        separated by the prompt string (qemu)
        Example:
        (qemu) running
        (qemu) rebooting
        will result in the returned value : [' running', ' rebooting']
        """
        msg = self.recv_data()
        return msg.split(self.DELIMITER_STRING)

    def send_command(self, cmd):
        self.socket.send(cmd.encode('utf-8'))
        self.socket.send(b"\r")
        print('[QEMU>>] %s' % (cmd))
        msgs = self.recv()
        for m in msgs:
            print('[QEMU<<] %s' % (m))
        return msgs

    def wait_for_state(self, s, retries=5):
        for _ in range(retries):
            msgs = self.send_command("info status")
            if len(msgs) <= 0 or len(msgs[0]) <= 0:
                time.sleep(1)
                continue
            for m in msgs:
                if s in m:
                    return True
        raise RuntimeError('Check state failed : %s' % (s))

    def wakeup(self):
        self.send_command("system_wakeup")

    def powerdown(self):
        self.send_command("system_powerdown")

    def __del__(self):
        if self.socket is not None:
            self.socket.close()


class QemuMachineService:
    QEMU_MACHINE_PORT_FWD = enum.auto()
    QEMU_MACHINE_MONITOR = enum.auto()
    QEMU_MACHINE_QMP = enum.auto()


class QemuMachine:
    debug_enabled = False
    # hold all qemu instances
    qemu_instances = []

    def __init__(self,
                 name='default',
                 machine=QemuEfiMachine.OVMF_Q35_TDX,
                 memory='2G',
                 service_blacklist=[]):
        self.name = name
        self.image_dir = '/var/tmp/tdxtest/'
        self.guest_initial_img = os.environ.get('TDXTEST_GUEST_IMG', f'{self.image_dir}/tdx-guest.qcow2')  # noqa: E501
        self._setup_workdir()
        self._create_image()

        # TODO : WA for log, to be removed
        print('\n\nQemuMachine created.')

        self.qcmd = QemuCommand(
            self.workdir_name,
            machine,
            memory
            )
        self.qcmd.add_image(self.image_path)
        self.qcmd.add_monitor()
        # monitor client associated to this machine
        # since there could be only one client, we keep track
        # of this client instance in the qemu machine object
        self.monitor = None
        self.qcmd.add_qmp()
        if QemuMachineService.QEMU_MACHINE_PORT_FWD not in service_blacklist:
            self.fwd_port = tcp_port_available()
            self.qcmd.add_port_forward(self.fwd_port)
        self.qcmd.add_qemu_run_log()

        self.proc = None
        self.out = None
        self.err = None

        QemuMachine.qemu_instances.append(self)

    @staticmethod
    def is_debug_enabled():
        return QemuMachine.debug_enabled

    @staticmethod
    def set_debug(debug : bool):
        QemuMachine.debug_enabled = debug

    @staticmethod
    def stop_all_running_qemus():
        for qemu in QemuMachine.qemu_instances:
            qemu.stop()

    def _create_image(self):
        # create an overlay image backed by the original image
        # See https://wiki.qemu.org/Documentation/CreateSnapshot
        self.image_path = f'{self.workdir_name}/image.qcow2'
        subprocess.check_call(f'qemu-img create -f qcow2 -b {self.guest_initial_img} -F qcow2 {self.image_path}',  # noqa: E501
                              stdout=subprocess.DEVNULL,
                              shell=True)

    def _setup_workdir(self):
        # if /run/user/ user folder exists, use it to store the work dir
        # if not use the default path for tempfile that is /tmp/
        run_path = pathlib.Path('/run/user/%d/' % (os.getuid()))
        if run_path.exists():
            tempfile.tempdir = str(run_path)
        # delete=False : we want to manage cleanup ourself for debugging
        #                purposes
        # delete parameter is only available from 3.12
        if (sys.version_info[0] == 3) and (sys.version_info[1] > 11):
            self.workdir = tempfile.TemporaryDirectory(prefix=f'tdxtest-{self.name}-', delete=False)  # noqa: E501
        else:
            self.workdir = tempfile.TemporaryDirectory(prefix=f'tdxtest-{self.name}-')  # noqa: E501
        self.workdir_name = self.workdir.name

    @property
    def pid(self):
        cs = subprocess.run(['cat', f'{self.workdir.name}/qemu.pid'], capture_output=True)  # noqa: E501
        assert cs.returncode == 0, 'Failed getting qemu pid'
        pid = int(cs.stdout.strip())
        return pid

    def rsync_file(self, fname, dest, sudo=False):
        """
        fname : local file or folder
        dest : destination folder (parent folder)
        """
        kv_user = 'root'
        kv_host = '127.0.0.1'
        kv_port = self.fwd_port
        ssh_opts = f'-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p {kv_port}'  # noqa: E501
        rsync_opts = '-atrv --delete --exclude="*~"'
        # use sshpass to pass clear text password for ssh
        rsync_opts += f' -e "sshpass -p 123456 ssh {ssh_opts}"'
        if sudo:
            rsync_opts += ' --rsync-path="sudo rsync"'
        subprocess.check_call(f'rsync {rsync_opts}  {fname} {kv_user}@{kv_host}:{dest}',  # noqa: E501
                              shell=True,
                              stdout=subprocess.DEVNULL)

    def run(self):
        """
        Run qemu
        """
        cmd = self.qcmd.get_command()
        print(' '.join(cmd))
        self.proc = subprocess.Popen(cmd,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)

    def run_and_wait(self):
        """
        Run qemu and wait for its start (by waiting for monitor file's availability)  # noqa: E501
        """
        self.run()
        QemuMonitor(self)

    def communicate(self, timeout=60):
        """
        Wait for qemu to exit
        """
        self.out, self.err = self.proc.communicate(timeout=timeout)
        if self.proc.returncode != 0:
            print(self.err.decode())
        return self.out, self.err

    def shutdown(self):
        """
        Send shutdown command to the VM
        Do not wait for the VM to exit
        Return false if the VM is already terminated
        """
        if self.proc is None:
            return False
        if self.proc.returncode is not None:
            return False

        try:
            mon = QemuMonitor(self)
            mon.powerdown()
        except Exception as e:
            print(f'Exception {e}')
            pass

        return True

    def stop(self):
        """
        Stop qemu process
        """
        if not self.shutdown():
            return

        try:
            # try to shutdown the VM properly, this is important to avoid
            # rootfs corruption if we want to run the guest again
            # catch exception and ignore it since we are stopping ....
            # no need to fail the test
            self.communicate()
            return
        except Exception as e:
            print(f'Exception {e}')

        print(f'Qemu process did not shutdown properly, terminate it ... ({self.workdir_name})')  # noqa: E501
        # terminate qemu process (SIGTERM)
        try:
            self.proc.terminate()
            self.communicate()
        except Exception as e:
            print(f'Exception {e}')

    def __del__(self):
        """
        Make sure we stop the qemu process if it is still running
        and clean up the working dir
        """
        self.stop()
        needs_cleanup = (not QemuMachine.is_debug_enabled())
        if needs_cleanup:
            self.workdir.cleanup()

        QemuMachine.qemu_instances.remove(self)

    def __enter__(self):
        """
        Context manager enter function
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Context manager exit function
        On context exit, we only stop the qemu process
        Other cleanup (workdir) is still delegated to object destruction
        hook, this is useful if we want to avoid these cleanup actions
        (test failure, debug flag, ...)
        """
        self.stop()


"""
MSR(Model Specific Register) Class

/dev/cpu/<num>/msr provides an interface to read and write the
model-specific registers (MSRs) of an x86 CPU.  CPUNUM is the
number of the CPU to access as listed in /proc/cpuinfo.

The register access is done by opening the file and seeking to
the MSR number as offset in the file, and then reading or writing
in chunks of 8 bytes.  An I/O transfer of more than 8 bytes means
multiple reads or writes of the same register.

This file is protected so that it can be read and written only by
the user root, or members of the group root.

For more information about the MSR, please read
https://man7.org/linux/man-pages/man4/msr.4.html
"""


class MSR:
    SGX_MCU_ERRORCODE = 0xa0
    SGX_DEBUG = 0x503
    IA32_FEATURE_CONTROL = 0x3a
    IA32_MKTME_PARTITIONING = 0x87
    IA32_TME_CAPABILITY = 0x981
    IA32_TME_ACTIVATE = 0x982


def _check_kmod():
    """
    Check whether the MSR is loaded, modprobe if not.
    """
    if not os.path.exists("/dev/cpu/0/msr"):
        os.system("modprobe msr")


def readmsr(msr, highbit=63, lowbit=0, cpu=0):
    """
    Read MSR register
    """
    assert abs(msr) < 0xffffffff
    assert os.geteuid() == 0, "need root priviledge"
    val = None
    fdobj = os.open(f'/dev/cpu/{cpu}/msr', os.O_RDONLY)
    os.lseek(fdobj, msr, os.SEEK_SET)
    val = struct.unpack('Q', os.read(fdobj, 8))[0]
    bits = highbit - lowbit + 1
    if bits < 64:
        val >>= lowbit
        val &= (1 << bits) - 1
    return val


class IntelTDXTest:
    def __init__(self):
        self.download_image()

    def test_boot_guest(self):
        with QemuMachine() as qm:
            qm.run_and_wait()

    def check_host_cpu(self):
        assert 'tdx_host_platform' in cpuinfo.get_cpu_info()['flags']
        assert 'sgx' in cpuinfo.get_cpu_info()['flags']

    def check_host_kernel(self):
        # when TDX is not properly loaded or initialized
        # this value should by 'N'
        # otherwise, the value 'Y' means tdx has been successfully initialized
        subprocess.check_call('grep Y /sys/module/kvm_intel/parameters/tdx',
                              shell=True)
        subprocess.check_call('grep Y /sys/module/kvm_intel/parameters/sgx',
                              shell=True)

        # Get dmesg and make sure it has the tdx module load message
        cs = subprocess.run(['sudo', 'dmesg'], check=True, capture_output=True)
        assert cs.returncode == 0, 'Failed getting dmesg'
        dmesg_str = cs.stdout.decode('utf-8')

        items = re.findall(r'virt/tdx: module initialized', dmesg_str)
        assert len(items) > 0

    def check_host_hardware(self):
        #
        # Check the bit 1 of MSR 0x982. 1 means MK-TME is enabled in BIOS.
        # SDM:
        #   Vol. 4 Model Specific Registers (MSRs)
        #     Table 2-2. IA-32 Architectural MSRs (Contd.)
        #       Register Address: 982H
        #       Architectural MSR Name: IA32_TME_ACTIVATE
        #       Bit Fields: 1
        #       Bit Description: Hardware Encryption Enable.
        #       This bit also enables TME-MK.
        #
        assert readmsr(0x982, 1, 1) == 1

        # Intel® Trust Domain CPU Architectural Extensions
        # IA32_SEAMRR_PHYS_BASE MSR
        # 11:11 : Enable bit for SEAMRR (SEAM Range Registers)
        assert readmsr(0x1401, 11, 11) == 1

        # Intel® Trust Domain CPU Architectural Extensions
        # IA32_TME_CAPABILITY MSR
        # 63:32 : NUM_TDX_PRIV_KEYS
        assert readmsr(0x87, 63, 32) > 16

    def download_image(self):
        """
        Downloads Cloud image
        """
        serie = '24.04'
        cloud_img = f'ubuntu-{serie}-server-cloudimg-amd64.img'
        full_url = f'https://cloud-images.ubuntu.com/releases/noble/release/{cloud_img}'  # noqa: E501
        dest_file = '/var/tmp/tdxtest/tdx-guest.qcow2'

        if not os.path.isdir('/var/tmp/tdxtest'):
            os.mkdir('/var/tmp/tdxtest')

        if os.path.isfile(dest_file):
            return False

        # Attempt download
        try:
            urllib.request.urlretrieve(full_url, dest_file)
        except (
            IOError,
            OSError,
            urllib.error.HTTPError,
            urllib.error.URLError,
        ) as exception:
            print(
                "Failed download of image from %s: %s", full_url, exception
            )
            return False

        if not os.path.isfile(dest_file):
            return False

        return dest_file


def main():
    """Main function."""
    description = "Intel TDX tests"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("check", choices=["check_host_hardware", "check_host_kernel", "check_host_cpu", "test_boot_guest"])  # noqa: E501
    args = parser.parse_args()
    return getattr(IntelTDXTest(), args.check)()


if __name__ == "__main__":
    sys.exit(main())
