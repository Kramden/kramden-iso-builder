#!/bin/bash
#
#
# Errors (e.g. a failed pull-ppa-debs or livefs-edit call) must abort the
# script. This is invoked from CI as `sudo ./kramden.sh ...`, a separate
# process with its own shebang -- GitHub Actions' default `-eo pipefail` on
# the workflow step's own shell can't see into it, so without set -e here a
# failure partway through is silently swallowed (the script's last command
# still exits 0) and the job reports success with a broken/incomplete ISO.
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
out=$(echo "${in//ubuntu/kramden}")
out=$(echo "${out//desktop/$date}")

echo "Fetching local debian packages"
rm -f $dir/debs/*
wget -O $dir/debs/google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

cd $dir/debs
# Without an explicit release, pull-ppa-debs defaults to Ubuntu's current
# development series (Launchpad's "devel" release) rather than the noble
# target this pipeline builds for, so pin it explicitly.
for p in kramden-desktop kramden-overrides kramden-provision; do pull-ppa-debs ppa:kramden-team/kramden $p noble; done

cd $dir

echo $out > kramden-iso

echo "Creating $out"
echo "Creating base image"
livefs-edit $in out/base.iso --action-yaml kramden.yaml
echo "Adding local debs to pool"
livefs-edit out/base.iso out/kramden.iso --add-debs-to-pool debs/*.deb --install-debs debs/kramden-overrides*deb
echo "Copying in autoinstall.yaml"
livefs-edit out/kramden.iso out/kramden2.iso --cp $PWD/autoinstall.yaml new/iso/autoinstall.yaml
rm -f out/kramden.iso
livefs-edit out/kramden2.iso out/kramden3.iso --cp $PWD/kramden-iso new/iso/kramden-iso
rm -f out/kramden2.iso
mv out/kramden3.iso $out

echo "$out created"
