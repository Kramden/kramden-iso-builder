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
# gpu-manager scans and probes GPU hardware before starting GDM (Before=display-manager.service).
# On some hardware it hangs indefinitely, preventing GDM from ever starting (blank screen at boot).
# The live ISO doesn't install proprietary GPU drivers so gpu-manager serves no purpose here.
ln -sf /dev/null "new/minimal/etc/systemd/system/gpu-manager.service"

# casper-md5check checksums the entire ISO on every boot — expensive I/O that
# saturates the CPU on slow hardware exactly when GDM is trying to start.
# Not needed for a spec testing image built from a known-good pipeline.
ln -sf /dev/null "new/minimal/etc/systemd/system/casper-md5check.service"

# Continuously stream the journal to a plain file so it can be read with cat/tail
# even when the system is too loaded for live journalctl.
# Access via: Ctrl+Alt+F2 then  tail -200 /tmp/kramden-journal.log
mkdir -p new/minimal/etc/systemd/system
cat > new/minimal/etc/systemd/system/kramden-journal-capture.service << 'EOF'
[Unit]
Description=Stream journal to /tmp for post-hang debugging
After=systemd-journald.service

[Service]
Type=simple
ExecStart=/bin/sh -c 'journalctl -f -o short-iso >> /tmp/kramden-journal.log'
Restart=no

[Install]
WantedBy=multi-user.target
EOF
ln -sf /etc/systemd/system/kramden-journal-capture.service \
    new/minimal/etc/systemd/system/multi-user.target.wants/kramden-journal-capture.service

# Mask heavyweight user services not needed for hardware spec testing
mkdir -p new/minimal/etc/systemd/user
for svc in \
    tracker-miner-fs-3.service tracker-extract-3.service tracker-writeback-3.service \
    evolution-source-registry.service evolution-calendar-factory.service \
    evolution-addressbook-factory.service evolution-user-prompter.service \
    goa-daemon.service goa-identity-service.service \
    gnome-remote-desktop.service; do
    ln -sf /dev/null "new/minimal/etc/systemd/user/${svc}"
done

# Mask system services not needed for hardware spec testing
for svc in \
    whoopsie.service colord.service ModemManager.service speech-dispatcher.service \
    apport.service; do
    ln -sf /dev/null "new/minimal/etc/systemd/system/${svc}"
done
ln -sf /dev/null "new/minimal/etc/systemd/system/whoopsie.path"

# apt-daily timers can fire on first boot and trigger package list fetches
# even when auto-upgrades are disabled in apt config.
for timer in apt-daily apt-daily-upgrade fwupd-refresh; do
    ln -sf /dev/null "new/minimal/etc/systemd/system/${timer}.timer"
done

# Autologin on tty2 so Ctrl+Alt+F2 always gives a shell for debugging.
# The ubuntu live user is created by casper in the initramfs, well before
# any getty unit fires, so the autologin target user will exist at runtime.
mkdir -p new/minimal/etc/systemd/system/getty@tty2.service.d
printf '[Service]\nExecStart=\nExecStart=-/sbin/agetty --autologin ubuntu --noclear %%I $TERM\n' \
    > new/minimal/etc/systemd/system/getty@tty2.service.d/autologin.conf
