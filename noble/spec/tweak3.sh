#!/bin/bash
#

############################ Third Run ############################################
#sed -i 's/google-chrome-stable/google-chrome-stable --password-store=basic/g' new/minimal.standard.live.custom/usr/share/applications/google-chrome.desktop
#sed -i 's|"\$@"$|"\$@" "--password-store=basic"|g' new/minimal.standard.live.custom/opt/google/chrome/google-chrome
rm -f new/*/etc/xdg/autostart/update-notifier.desktop || true
sed -i 's/1/0/g' new/*/etc/apt/apt.conf.d/20auto-upgrades || true
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

printf '#!/bin/bash\nnmcli device wifi connect "Kramden Guest" password "%s" name kramden-guest 2>/dev/null || true\n' "$KRAMDEN_GUEST_WIFI" > new/minimal.standard.live.custom/usr/bin/wifi.sh
printf 'nmcli device wifi connect "Kramden_Guest" password "Kramden1!" name kramden-guest2 2>/dev/null || true\n' >> new/minimal.standard.live.custom/usr/bin/wifi.sh
chmod a+x new/minimal.standard.live.custom/usr/bin/wifi.sh

cat << 'EOF' > new/minimal.standard.live.custom/etc/rc.local
#!/bin/bash
echo "Running asset.sh" >> /var/log/rc_local
/usr/share/kramden-provision/scripts/asset.sh >> /var/log/rc_local
EOF
chmod a+x new/minimal.standard.live.custom/etc/rc.local
# Noble only: force Xorg so GDM works on hardware where Wayland compositor fails silently.
# Revisit when rebasing on 26.04 (Xorg gone) — fix will need proper GPU firmware instead.
mkdir -p new/minimal.standard.live.custom/etc/gdm3
cat << 'EOF' > new/minimal.standard.live.custom/etc/gdm3/custom.conf
[daemon]
WaylandEnable=false
AutomaticLoginEnable=true
AutomaticLogin=ubuntu
EOF
mkdir -p new/minimal.standard.live.custom/etc/environment.d
echo "SORTLY_API_KEY=$SORTLY_API_KEY" >> new/minimal.standard.live.custom/etc/environment
