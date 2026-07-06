#!/bin/bash
#
############################ First Run ############################################

rm new/iso/casper/{minimal.standard.enhanced-secureboot.*,minimal.enhanced-secureboot.*,minimal.de.squashfs,minimal.es.squashfs,minimal.fr.squashfs,minimal.it.squashfs,minimal.pt.squashfs,minimal.ru.squashfs,minimal.standard.es.squashfs,minimal.standard.fr.squashfs,minimal.standard.it.squashfs,minimal.standard.pt.squashfs,minimal.standard.ru.squashfs,minimal.standard.zh.squashfs,minimal.zh.squashfs}
rm -rf new/iso/pool/*
rm new/minimal.standard.live/var/lib/snapd/desktop/applications/ubuntu-desktop-bootstrap_ubuntu-desktop-bootstrap.desktop
rm -rf new/minimal.standard.live/snap/ubuntu-desktop-bootstrap
rm new/minimal.standard.live/snap/bin/*
rm -rf new/minimal.standard.live/var/snap/ubuntu-desktop-bootstrap
rm new/{minimal.standard.live/var/lib/snapd/snaps/ubuntu-desktop-bootstrap*.snap,minimal.standard.live/var/lib/snapd/seed/snaps/ubuntu-desktop-bootstrap*.snap,minimal.standard.live/etc/systemd/system/*bootstrap*}
rm new/minimal.standard.live/var/lib/snapd/seed/seed.yaml
wget -O new/minimal.standard.live/usr/bin/screen-test https://github.com/kenvandine/screen-test/releases/download/0.3/screen-test
chmod a+x new/minimal.standard.live/usr/bin/screen-test
rm -rf new/minimal.standard.live/var/{cache,lib}/snapd new/minimal.standard.live/snap new/minimal.standard.live/etc/systemd/system/*snap*
for svc in snapd snapd.hold snapd.socket snapd.seeded snapd.autoimport snapd.recovery-chooser-trigger; do
    ln -sf /dev/null "new/minimal.standard.live/etc/systemd/system/${svc}.service" 2>/dev/null || true
done
ln -sf /dev/null "new/minimal.standard.live/etc/systemd/system/snapd.socket" 2>/dev/null || true
sed -i 's/Try or Install Ubuntu/Kramden Spec/g' new/iso/boot/grub/grub.cfg
sed -i 's/Ubuntu/Kramden Spec/g' new/iso/boot/grub/grub.cfg
sed -i 's/splash/splash toram noprompt noeject/g' new/iso/boot/grub/grub.cfg
sed -i 's/30/3/g' new/iso/boot/grub/grub.cfg

# Duplicate the first "Kramden Spec" entry without toram for devices with only 4G RAM
python3 - new/iso/boot/grub/grub.cfg << 'PYEOF'
import sys
path = sys.argv[1]
with open(path) as f:
    content = f.read()
lines = content.split('\n')
result = []
i = 0
inserted = False
while i < len(lines):
    line = lines[i]
    if not inserted and 'menuentry "Kramden Spec" {' in line:
        block = [line]
        depth = line.count('{') - line.count('}')
        j = i + 1
        while j < len(lines) and depth > 0:
            block.append(lines[j])
            depth += lines[j].count('{') - lines[j].count('}')
            j += 1
        result.extend(block)
        ram_block = [
            l.replace('menuentry "Kramden Spec" {', 'menuentry "Kramden Spec (4G RAM)" {')
             .replace(' toram', '')
            for l in block
        ]
        result.append('')
        result.extend(ram_block)
        inserted = True
        i = j
    else:
        result.append(line)
        i += 1
with open(path, 'w') as f:
    f.write('\n'.join(result))
PYEOF
