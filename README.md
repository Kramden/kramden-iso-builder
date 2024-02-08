# Updating base ISO

NOTE: throughout this guide, replace "input.iso" and "output.iso" with desired 
file names Run some basic setup, based on the released Ubuntu desktop ISO.  The 
goal is to create a customized ISO with the desired version of 
ubuntu-desktop-installer, some extra packages, and additional snaps seeded in 
the minimal.squashfs.  Once the base ISO is created, we can update specific 
components as needed with livefs-editor, just ensure that the kramden-iso 
file is updated each time and the resulting ISO file is versioned to match.

```
sudo livefs-editor input.iso output.iso --action-yaml kramden.yaml
```

Download updated snaps into the snaps directory
Update snaps/seed.yaml to match snap revisions downloaded

```
sudo python3 -m livefs_edit input.iso output.iso --edit-squashfs minimal --shell
```

in the livefs-edit shell
```
cp $dir/preseed/seed.yaml to new/minimal/var/lib/snapd/seed/
cp $dir/preseed/assertions/*.assert to new/minimal/var/lib/snapd/seed/assertions/
cp $dir/preseed/snaps/*.snap to new/minimal/var/lib/snapd/seed/snaps/
/snap/snapd/current/usr/lib/snapd/snap-preseed --reset new/minimal
/snap/snapd/current/usr/lib/snapd/snap-preseed new/minimal
```

Exit shell to save output.iso


```
sudo livefs-editor input.iso output.iso --cp $PWD/autoinstall.yaml new/iso/autoinstall.yaml
sudo livefs-editor input.iso output.iso --install-debs debs/kramden-overrides*.deb
sudo livefs-editor input.iso output.iso --add-debs-to-pool debs/*.deb
```
