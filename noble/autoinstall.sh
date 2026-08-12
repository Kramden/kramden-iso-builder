#!/bin/bash
#
#
if [ $# -lt 2 ];
then
        echo "USAGE: $0 SOURCE_ISO TARGET_DISK_IMG"
        exit
fi

source=$1
target=$2

echo "Creating new disk image $target"
qemu-img create -f qcow2 -o preallocation=off $target 20G
echo "Disk image $target created"

# Boot the build VM under OVMF (UEFI) firmware instead of QEMU's default
# SeaBIOS/legacy mode. Ubuntu's installer detects the firmware it's running
# under and partitions accordingly: under legacy BIOS it never creates an EFI
# System Partition, which leaves the resulting disk unbootable on UEFI-only
# target hardware (no CSM/legacy fallback). Under UEFI, curtin's default
# storage layout creates a GPT ESP and installs grub-efi/shim, and also
# writes the removable fallback path (/EFI/BOOT/BOOTX64.EFI) so the disk
# boots even on hardware whose NVRAM has no matching boot entry -- exactly
# the scenario when this image gets cloned onto different physical machines.
ovmf_code=/usr/share/OVMF/OVMF_CODE_4M.fd
ovmf_vars_template=/usr/share/OVMF/OVMF_VARS_4M.fd
if [ ! -f "$ovmf_code" ] || [ ! -f "$ovmf_vars_template" ]; then
        echo "OVMF firmware not found at $ovmf_code / $ovmf_vars_template. Install the 'ovmf' package." >&2
        exit 1
fi

# Per-build writable copy of the UEFI NVRAM template; qemu writes boot
# variables to this file as the install progresses.
ovmf_vars="${target}.OVMF_VARS.fd"
cp "$ovmf_vars_template" "$ovmf_vars"

echo "Automated install starting... please wait"
qemu-system-x86_64 \
            -enable-kvm \
            -m 8G \
            -cpu host \
            -smp 8 \
            -drive if=pflash,format=raw,unit=0,file=$ovmf_code,readonly=on \
            -drive if=pflash,format=raw,unit=1,file=$ovmf_vars \
            -hda $target \
            -cdrom $source \
            -boot d \
            -nographic # Run in headless mode for CI
echo "Automated install $target complete, booting once to prime... please wait"

qemu-system-x86_64 \
            -enable-kvm \
            -m 8G \
            -cpu host \
            -smp 8 \
            -drive if=pflash,format=raw,unit=0,file=$ovmf_code,readonly=on \
            -drive if=pflash,format=raw,unit=1,file=$ovmf_vars \
            -hda $target \
            -nographic # Run in headless mode for CI
echo "System image $target is ready to be deployed"

rm -f "$ovmf_vars"
