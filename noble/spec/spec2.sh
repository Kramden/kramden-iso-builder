#!/bin/bash
#
#
# See noble/kramden.sh for why this needs its own set -e: it's invoked from
# CI as a separate script process, so the workflow step's own -eo pipefail
# can't see failures inside it.
set -euo pipefail

dir=$(dirname $(realpath $0))
in=$1

if [ $UID != 0 ];
then
	echo "Must be run with root privileges, for example with sudo"
	exit 1
fi

if [ $# -lt 1 ];
then
	echo "USAGE: sudo $0 SOURCE_ISO"
	exit 1
fi

if [ -z "$SORTLY_API_KEY" ]; then
    echo "ERROR: SORTLY_API_KEY is not set!"
    exit 1
fi

if [ -z "$KRAMDEN_GUEST_WIFI" ]; then
    echo "ERROR: KRAMDEN_GUEST_WIFI is not set!"
    exit 1
fi

if [ -d $dir/out ];
then
    rm -f $dir/out/*
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
livefs-edit $in out/spec0.iso --add-apt-repository ppa:kramden-team/kramden-test --install-packages git guvcview python3-psutil python3-pyudev python3-reportlab python3-requests kramden-device kramden-provision kramden-spec nvme-cli cheese nwipe
livefs-edit out/spec0.iso out/spec1.iso --install-debs debs/{srvadmin*,command*,firefox*}.deb
rm -f out/spec0.iso
livefs-edit out/spec1.iso out/spec2.iso --cp $PWD/kramden-spec-iso new/iso/kramden-spec-iso
rm -f out/spec1.iso
livefs-edit out/spec2.iso out/spec3.iso --edit-squashfs minimal.standard.live false --shell $dir/tweak1.sh || true
rm -f out/spec2.iso
livefs-edit out/spec3.iso out/spec4.iso --edit-squashfs minimal false --shell $dir/tweak2.sh || true
livefs-edit out/spec4.iso out/spec5.iso --edit-squashfs minimal.standard.live.custom false --shell $dir/tweak3.sh || true
rm -f out/spec4.iso
mv out/spec5.iso $out

echo "$out created"
