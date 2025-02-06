#!/bin/bash
#
#
# Specify verion of kramden-overrides debian package available from
# https://launchpad.net/~kramden-team/+archive/ubuntu/kramden
DESKTOP_VERSION=0.0.5-ppa1~ubuntu24.04
OVERRIDES_VERSION=0.5.4-ppa1~ubuntu24.04

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
out=$(echo "${in//ubuntu/kramden}")
out=$(echo "${out//base/$date}")

echo "Fetching local debian packages"
wget -O $dir/debs/google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
wget -O $dir/debs/kramden-desktop_${DESKTOP_VERSION}_amd64.deb https://launchpad.net/~kramden-team/+archive/ubuntu/kramden/+files/kramden-desktop_${DESKTOP_VERSION}_amd64.deb
wget -O $dir/debs/kramden-overrides_${OVERRIDES_VERSION}_amd64.deb https://launchpad.net/~kramden-team/+archive/ubuntu/kramden/+files/kramden-overrides_${OVERRIDES_VERSION}_amd64.deb

cd $dir
echo $out > kramden-iso

echo "Creating $out"
echo "Creating base image"
livefs-editor $in out/base.iso --action-yaml kramden.yaml
echo "Adding local debs to pool"
livefs-editor out/base.iso out/kramden.iso --add-debs-to-pool debs/*.deb --install-debs debs/kramden-overrides*deb
echo "Copying in autoinstall.yaml"
livefs-editor out/kramden.iso out/kramden2.iso --cp $PWD/autoinstall.yaml new/iso/autoinstall.yaml
rm -f out/kramden.iso
livefs-editor out/kramden2.iso out/kramden3.iso --cp $PWD/kramden-iso new/iso/kramden-iso
rm -f out/kramden2.iso
mv out/kramden3.iso $out

echo "$out created"
