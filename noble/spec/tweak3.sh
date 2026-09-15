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
echo "SORTLY_FOLDER_LOOKUP_URL=$SORTLY_FOLDER_LOOKUP_URL" >> new/minimal.standard.live.custom/etc/environment
# SORTLY_FOLDER_LOOKUP_API_KEY is deliberately NOT written to /etc/environment:
# PAM's pam_env parser (_parse_env_file in pam_env.c) scans each line for an
# unescaped '#' and truncates the value there *before* it even looks at
# surrounding quotes, so a key like "QN#xxxx" gets chopped down to "QN" with
# no way to escape the '#'. /etc/environment.d below uses systemd's parser,
# which keeps '#' inside quotes intact, so that's the only place this key
# is safe to store.
# kramden-spec is launched via XDG autostart, which systemd-xdg-autostart-generator
# turns into a systemd --user unit. Those units get their environment from
# /etc/environment.d, not from /etc/environment (which is PAM-only and only reaches
# login-shell/session processes) — so the vars must also be dropped here or the
# autostarted app never sees them even though a manually sourced terminal does.
cat << EOF > new/minimal.standard.live.custom/etc/environment.d/50-kramden-spec.conf
SORTLY_API_KEY="$SORTLY_API_KEY"
SORTLY_FOLDER_LOOKUP_URL="$SORTLY_FOLDER_LOOKUP_URL"
SORTLY_FOLDER_LOOKUP_API_KEY="$SORTLY_FOLDER_LOOKUP_API_KEY"
EOF
