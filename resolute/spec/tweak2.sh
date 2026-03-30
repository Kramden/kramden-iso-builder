#!/bin/bash
#

############################ Second Run ############################################
rm new/minimal/var/lib/snapd/desktop/applications/ubuntu-desktop-bootstrap_ubuntu-desktop-bootstrap.desktop
rm -rf new/minimal/snap/ubuntu-desktop-bootstrap
rm new/minimal/snap/bin/*
rm -rf new/minimal/var/snap/ubuntu-desktop-bootstrap
rm new/{minimal/var/lib/snapd/snaps/ubuntu-desktop-bootstrap*.snap,minimal/var/lib/snapd/seed/snaps/ubuntu-desktop-bootstrap*.snap,minimal/etc/systemd/system/*bootstrap*}
rm new/minimal/var/lib/snapd/seed/seed.yaml
rm -rf new/minimal/var/{cache,lib}/snapd new/minimal/snap new/minimal/etc/systemd/system/*snap*
rm -rf new/minimal/usr/lib/libreoffice new/minimal/usr/bin/libreoffice
rm -rf new/minimal/usr/share/locale-langpack
#echo WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1 >> new/minimal/etc/environment
rm new/minimal/etc/xdg/autostart/org.kramden.device.desktop
rm -f new/*/etc/xdg/autostart/update-notifier.desktop || true
sed -i 's/1/0/g' new/*/etc/apt/apt.conf.d/20auto-upgrades || true
echo kernel.apparmor_restrict_unprivileged_unconfined=0 > new/minimal/etc/sysctl.d/99-kramden-local.conf
echo kernel.apparmor_restrict_unprivileged_userns=0 >> new/minimal/etc/sysctl.d/99-kramden-local.conf
