#!/bin/bash
#
#

dir=$(dirname $(realpath $0))
in=$1

if [ $UID != 0 ];
then
	echo "Must be run with root privileges, for example with sudo"
	exit
fi

if [ $# -lt 1 ];
then
	echo "USAGE: sudo $0 SOURCE_ISO"
	exit
fi

if [ -d $dir/out ];
then
    rm $dir/out/* 2>/dev/null
else
    mkdir $dir/out
fi

if [ ! -d $dir/debs ];
then
    mkdir $dir/debs
fi

date=$(date "+%Y%m%d-%H%M")

# Output file should be kramden-UBUNTUVERSION-DATE-HOUR:MINUTE-ARCH.iso
out=$(echo "${in//ubuntu/kramden-spec}")
out=$(echo "${out//desktop/$date}")

echo "Fetching local debian packages"
#rm $dir/debs/*
#cd $dir/debs
#for p in kramden-overrides; do pull-ppa-debs ppa:kramden-team/kramden $p; done

cd $dir

echo $out > kramden-spec-iso

echo "Creating $out"
echo "Creating base image"
#livefs-edit $in out/base.iso --action-yaml spec.yaml
echo "Adding local debs to pool"
livefs-edit $in out/spec0.iso --add-apt-repository ppa:kramden-team/kramden-test --install-packages guvcview python3-psutil python3-pyudev python3-reportlab python3-requests kramden-device kramden-provision kramden-spec nvme-cli cheese nwipe
livefs-edit out/spec0.iso out/spec1.iso --install-debs debs/{srvadmin*,command*,firefox*}.deb
rm -f out/spec0.iso
livefs-edit out/spec1.iso out/spec2.iso --cp $PWD/kramden-spec-iso new/iso/kramden-spec-iso
rm -f out/spec1.iso
sudo livefs-editor out/spec2.iso out/spec3.iso --edit-squashfs minimal.standard.live false --shell
rm -f out/spec2.iso
sudo livefs-editor out/spec3.iso out/spec4.iso --edit-squashfs minimal false --shell
sudo livefs-editor out/spec4.iso out/spec5.iso --edit-squashfs minimal.standard.live.custom false --shell
rm -f out/spec4.iso
mv out/spec5.iso $out

echo "$out created"
