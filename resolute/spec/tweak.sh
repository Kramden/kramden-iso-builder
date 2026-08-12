#!/bin/bash
#
rm new/iso/casper/{minimal.standard.enhanced-secureboot.*,minimal.enhanced-secureboot.*,minimal.de.squashfs,minimal.es.squashfs,minimal.fr.squashfs,minimal.it.squashfs,minimal.pt.squashfs,minimal.ru.squashfs,minimal.standard.es.squashfs,minimal.standard.fr.squashfs,minimal.standard.it.squashfs,minimal.standard.pt.squashfs,minimal.standard.ru.squashfs,minimal.standard.zh.squashfs,minimal.zh.squashfs}
rm -rf new/iso/pool/*
rm new/minimal.standard.live/var/lib/snapd/desktop/applications/ubuntu-desktop-bootstrap_ubuntu-desktop-bootstrap.desktop
rm -rf new/minimal.standard.live/snap/ubuntu-desktop-bootstrap
rm new/minimal.standard.live/snap/bin/*
rm -rf new/minimal.standard.live/var/snap/ubuntu-desktop-bootstrap
rm new/{minimal.standard.live/var/lib/snapd/snaps/ubuntu-desktop-bootstrap*.snap,minimal.standard.live/var/lib/snapd/seed/snaps/ubuntu-desktop-bootstrap*.snap,minimal.standard.live/etc/systemd/system/*bootstrap*}
rm new/minimal.standard.live/var/lib/snapd/seed/seed.yaml
cp /snap/screen-test/current/usr/bin/screen-test new/minimal.standard.live/usr/bin/
rm -rf new/minimal.standard.live/var/{cache,lib}/snapd new/minimal.standard.live/snap new/minimal.standard.live/etc/systemd/system/*snap*
sed -i 's/Try or Install Ubuntu/Kramden Spec/g' new/iso/boot/grub/grub.cfg
sed -i 's/Ubuntu/Kramden Spec/g' new/iso/boot/grub/grub.cfg
sed -i 's/30/3/g' new/iso/boot/grub/grub.cfg

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
echo kernel.apparmor_restrict_unprivileged_unconfined=0 > new/minimal/etc/sysctl.d/99-kramden-local.conf
echo kernel.apparmor_restrict_unprivileged_userns=0 >> new/minimal/etc/sysctl.d/99-kramden-local.conf

############################ Third Run ############################################
#sed -i 's/google-chrome-stable/google-chrome-stable --password-store=basic/g' new/minimal.standard.live.custom/usr/share/applications/google-chrome.desktop
#sed -i 's|"\$@"$|"\$@" "--password-store=basic"|g' new/minimal.standard.live.custom/opt/google/chrome/google-chrome
mkdir -p new/minimal.standard.live.custom/etc/xdg/autostart
cat << 'EOF' > new/minimal.standard.live.custom/etc/xdg/autostart/org.kramden.wifi.desktop
[Desktop Entry]
Type=Application
Version=1.0
Name=Kramden Spec Wifi
Comment=Kramden Spec Wifi
Keywords=kramden;setup;
Exec=wifi.sh
Icon=kramden
Terminal=false
Categories=Utility;
NoDisplay=true
EOF

printf '#!/bin/bash\nnmcli device wifi connect "Kramden Speccing" password "%s" name kramden-speccing 2>/dev/null || true\n' "$KRAMDEN_SPEC_WIFI" > new/minimal.standard.live.custom/usr/bin/wifi.sh
chmod a+x new/minimal.standard.live.custom/usr/bin/wifi.sh

cat << 'EOF' > new/minimal.standard.live.custom/etc/rc.local
#!/bin/bash
echo "Running asset.sh" >> /var/log/rc_local
/usr/share/kramden-provision/scripts/asset.sh >> /var/log/rc_local
EOF
chmod a+x new/minimal.standard.live.custom/etc/rc.local
mkdir -p new/minimal.standard.live.custom/etc/environment.d
echo "SORTLY_API_KEY=sk_sortly_FAXkCyGsiD-9AEV16yaW" >> new/minimal.standard.live.custom/etc/environment
