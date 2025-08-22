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
qemu-img create -f raw -o preallocation=off $target 20G
echo "Disk image $target created"

echo "Automated install starting... please wait"
qemu-system-x86_64 \
            -enable-kvm \
            -m 8G \
            -cpu host \
            -smp 8 \
            -drive file=$target,format=raw,media=disk \
            -cdrom $source \
            -boot d \
            -nographic # Run in headless mode for CI
echo "Automated install $target complete, booting once to prime... please wait"

qemu-system-x86_64 \
            -enable-kvm \
            -m 8G \
            -cpu host \
            -smp 8 \
            -drive file=$target,format=raw,media=disk \
            -nographic # Run in headless mode for CI
echo "System image $target is ready to be deployed"
