#!/bin/bash
#
############################ minimal.standard layer ############################################

rm -rf new/minimal.standard/var/{cache,lib}/snapd new/minimal.standard/var/snap new/minimal.standard/snap
rm -rf new/minimal.standard/lib/systemd/system/snapd* new/minimal.standard/usr/lib/systemd/system/snapd*
rm -rf new/minimal.standard/usr/lib/systemd/system-environment-generators/snapd*
rm -rf new/minimal.standard/usr/lib/systemd/user/snapd* new/minimal.standard/usr/lib/systemd/user/sockets.target.wants/snapd*
rm -rf new/minimal.standard/etc/systemd/system/*snap* new/minimal.standard/etc/systemd/system/*/*snap*
