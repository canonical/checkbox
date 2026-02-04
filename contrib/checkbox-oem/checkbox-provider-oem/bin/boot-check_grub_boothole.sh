#!/bin/bash

cleanup()
{
    echo "Please refer to https://docs.google.com/document/d/1EheQcQ5fzdwW_JOXz5LChqObu6di4GztkxRtVxtUYGs/edit#heading=h.ek2fnosafgow for this test case."
}

trap cleanup EXIT HUP INT QUIT TERM

case "$(lsb_release -cs)" in
    (focal)
        if ! sbverify --list "/boot/vmlinuz-$(uname -r)" | grep -oP "Secure Boot Signing (.*)"; then
            echo "/boot/vmlinuz-$(uname -r) has invalid signature for Secure Boot."
            exit 1
        fi
        TARGET_GRUB="2.04-1ubuntu26.1"
        case "$(uname -r)" in
            (5.4.0-*-generic)
                TARGET_KERNEL=5.4.0-31-generic
                ;;
            (5.6.0-*-oem)
                TARGET_KERNEL=5.6.0-1011-oem
                ;;
            (5.8.0-*-generic)
                TARGET_KERNEL=5.8.0-23-generic
                ;;
            (5.10.0-*-oem)
                TARGET_KERNEL=5.10.0-1002-oem
                ;;
            (5.11.0-*-generic)
                TARGET_KERNEL=5.11.0-23-generic
                ;;
            (5.13.0-*-oem)
                TARGET_KERNEL=5.13.0-1003-oem
                ;;
            (5.14.0-*-oem)
                TARGET_KERNEL=5.14.0-1002-oem
                ;;
            (5.15.0-*-generic)
                TARGET_KERNEL=5.15.0-46-generic
                ;;
            (*)
                echo "Linux kernel '$(uname -r)' is not in the check list yet. Please report the bug."
                exit 1
                ;;
        esac
        ;;
    (bionic)
        TARGET_GRUB="2.02-2ubuntu8.17"
        case "$(uname -r)" in
            (4.15.0-*-generic)
                TARGET_KERNEL=4.15.0-101-generic
                ;;
            (4.18.0-*-generic)
                echo "There is no valid signature for 4.18.0-*-generic kernel."
                exit 1
                ;;
            (4.15.0-*-oem)
                TARGET_KERNEL=4.15.0-1087-oem
                ;;
            (5.0.0-*-oem-osp1)
                TARGET_KERNEL=5.0.0-1059-oem-osp1
                ;;
            (5.0.0-*-generic)
                TARGET_KERNEL=5.0.0-52-generic
                ;;
            (5.3.0-*-generic)
                TARGET_KERNEL=5.3.0-53-generic
                ;;
            (5.4.0-*-generic)
                TARGET_KERNEL=5.4.0-37-generic
                ;;
            (*)
                echo "Linux kernel '$(uname -r)' is not in the check list yet. Please report the bug."
                exit 1
                ;;
        esac
        ;;
    (xenial)
        TARGET_GRUB="2.02~beta2-36ubuntu3.26"
        case "$(uname -r)" in
            (4.4.0-*-generic)
                TARGET_KERNEL=4.4.0-184-generic
                ;;
            (4.8.0-*-generic)
                echo "There is no valid signature for 4.8.0-*-generic kernel."
                exit 1
                ;;
            (4.10.0-*-generic)
                echo "There is no valid signature for 4.10.0-*-generic kernel."
                exit 1
                ;;
            (4.11.0-*-generic)
                echo "There is no valid signature for 4.11.0-*-generic kernel."
                exit 1
                ;;
            (4.13.0-*-generic)
                echo "There is no valid signature for 4.13.0-*-generic kernel."
                exit 1
                ;;
            (4.13.0-*-oem)
                echo "There is no valid signature for 4.13.0-*-oem kernel."
                exit 1
                ;;
            (4.15.0-*-generic)
                TARGET_KERNEL=4.15.0-101-generic
                ;;
            (*)
                echo "Linux kernel '$(uname -r)' is not in the check list yet. Please report the bug."
                exit 1
                ;;
        esac
        ;;
    (*)
        echo "'$(lsb_release -ds)' is not in the check list yet. Please report the bug."
        exit 1
        ;;
esac

CURRENT=$(dpkg-query -W -f='${Version}\n' grub-efi-amd64-bin)
RECOVERY_PART="yes"

if [ -z "$CURRENT" ]; then
    echo "Can not find grub-efi-amd64 version."
    exit 1
fi

if dpkg --compare-versions "$CURRENT" lt "$TARGET_GRUB"; then
    echo "GRUB version needs to be $TARGET_GRUB at least, but it is $CURRENT now."
    exit 1
fi

if dpkg --compare-versions "$(uname -r)" lt "$TARGET_KERNEL"; then
    echo "Kernel version needs to be $TARGET_KERNEL at least, but it is $(uname -r) now."
    exit 1
fi

# Check the GRUB EFI file in the recovery partition
if dpkg-query -W -f='${Status}\n' dell-recovery 2>&1 | grep "install ok installed" >/dev/null 2>&1; then
    TARGET=$(python3 -c "import Dell.recovery_common as magic; target=magic.find_partition(); print(target.decode('utf8')) if type(target) is bytes else print(target)")
elif dpkg-query -W -f='${Status}\n' ubuntu-recovery 2>&1 | grep "install ok installed" >/dev/null 2>&1; then
    TARGET=$(python3 -c "import ubunturecovery.recovery_common as magic; target=magic.find_partition('PQSERVICE'); print(target.decode('utf8')) if type(target) is bytes else print(target)")
else
    echo "There is no dell-recovery or ubuntu-recovery partition in this system."
    echo "Skip to check recovery partition."
    RECOVERY_PART="no"
fi

DISK=$(mktemp -d)

clean_up ()
{
    cd /
    umount "$DISK"
    rmdir "$DISK"
}

if [ "$RECOVERY_PART" = "yes" ]; then
    trap clean_up EXIT
    mount "$TARGET" "$DISK"
    cd "$DISK" || exit
fi

for efi in /boot/efi/EFI/ubuntu/grubx64.efi efi.factory/boot/grubx64.efi efi/boot/grubx64.efi; do
    if [ -f "$efi" ]; then
        VERSION=$(strings "$efi" | grep "^${TARGET_GRUB:0:12}")
        if dpkg --compare-versions "$VERSION" lt "$TARGET_GRUB"; then
            echo "The version of grubx64.efi in the recovery partition needs to be $TARGET_GRUB at least, but it is $VERSION now."
            exit 1
        fi
    fi
done
