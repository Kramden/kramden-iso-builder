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
for svc in snapd snapd.hold snapd.socket snapd.seeded snapd.autoimport snapd.recovery-chooser-trigger; do
    ln -sf /dev/null "new/minimal/etc/systemd/system/${svc}.service" 2>/dev/null || true
done
ln -sf /dev/null "new/minimal/etc/systemd/system/snapd.socket" 2>/dev/null || true
rm -rf new/minimal/usr/lib/libreoffice new/minimal/usr/bin/libreoffice
rm -rf new/minimal/usr/share/locale-langpack
#echo WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1 >> new/minimal/etc/environment
rm new/minimal/etc/xdg/autostart/org.kramden.device.desktop
rm -f new/*/etc/xdg/autostart/update-notifier.desktop || true
sed -i 's/1/0/g' new/*/etc/apt/apt.conf.d/20auto-upgrades || true
echo kernel.apparmor_restrict_unprivileged_unconfined=0 > new/minimal/etc/sysctl.d/99-kramden-local.conf
echo kernel.apparmor_restrict_unprivileged_userns=0 >> new/minimal/etc/sysctl.d/99-kramden-local.conf
# Noble only: force Xorg in GDM. On some hardware GDM fails to start under Wayland
# (blank display). /etc/gdm3/custom.conf ships in the base 'minimal' layer, so it
# must be patched here, not in the live/custom overlays where the file is absent.
# Uncomment the existing template line in place so casper's 15autologin sed (which
# matches the surrounding "#  AutomaticLogin = user1" template lines to set up
# auto-login) keeps working. Revisit when rebasing on 26.04 (Xorg gone).
GDM_CONF=new/minimal/etc/gdm3/custom.conf
[ -f "$GDM_CONF" ] && sed -i 's/^#WaylandEnable=false$/WaylandEnable=false/' "$GDM_CONF"

# gpu-manager scans and probes GPU hardware before starting GDM (Before=display-manager.service).
# On some hardware it hangs indefinitely, preventing GDM from ever starting (blank screen at boot).
# The live ISO doesn't install proprietary GPU drivers so gpu-manager serves no purpose here.
ln -sf /dev/null "new/minimal/etc/systemd/system/gpu-manager.service"

# Pre-create AccountsService entry for the ubuntu live user so GDM auto-login
# picks the X11 Ubuntu session explicitly rather than falling back to whatever
# its default would be with no session history.
mkdir -p new/minimal/var/lib/AccountsService/users
printf '[User]\nXSession=ubuntu\nIcon=\n' > new/minimal/var/lib/AccountsService/users/ubuntu
