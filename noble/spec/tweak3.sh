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

printf '#!/bin/bash\nnmcli device wifi connect "Kramden Speccing" password "%s" name kramden-speccing 2>/dev/null || true\n' "$KRAMDEN_SPEC_WIFI" > new/minimal.standard.live.custom/usr/bin/wifi.sh
printf 'nmcli device wifi connect "Kramden_Guest" password "Kramden1!" name kramden-guest2 2>/dev/null || true\n' >> new/minimal.standard.live.custom/usr/bin/wifi.sh
chmod a+x new/minimal.standard.live.custom/usr/bin/wifi.sh

cat << 'EOF' > new/minimal.standard.live.custom/etc/rc.local
#!/bin/bash
echo "Running asset.sh" >> /var/log/rc_local
/usr/share/kramden-provision/scripts/asset.sh >> /var/log/rc_local
EOF
chmod a+x new/minimal.standard.live.custom/etc/rc.local
# Note: the GDM Xorg fix lives in tweak2.sh — /etc/gdm3/custom.conf ships in the
# base 'minimal' layer, not in this custom overlay.
mkdir -p new/minimal.standard.live.custom/etc/environment.d
echo "SORTLY_API_KEY=$SORTLY_API_KEY" >> new/minimal.standard.live.custom/etc/environment
echo "SORTLY_FOLDER_LOOKUP_URL=$SORTLY_FOLDER_LOOKUP_API_URL" >> new/minimal.standard.live.custom/etc/environment
echo "SORTLY_FOLDER_LOOKUP_API_KEY=$SORTLY_FOLDER_LOOKUP_API_KEY" >> new/minimal.standard.live.custom/etc/environment
