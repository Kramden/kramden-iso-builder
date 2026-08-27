#!/bin/bash
#
# One-time setup: installs livefs-editor (https://github.com/mwhudson/livefs-editor)
# into a local venv, for manually patching an existing Kramden ISO (e.g.
# swapping in autoinstall.yaml) without needing a full CI rebuild.
set -euo pipefail

dir=$(dirname $(realpath $0))
venv=$dir/venv

echo "Installing system dependencies"
sudo apt update
sudo apt install -y xorriso squashfs-tools python3-debian mount python3-venv git

if [ ! -d "$venv" ]; then
    echo "Creating venv at $venv"
    # --system-site-packages so the venv can see the apt-installed
    # python3-debian module used by livefs-editor; it isn't reliably
    # pip-installable on its own.
    python3 -m venv --system-site-packages "$venv"
fi

src=$(mktemp -d)
trap 'rm -rf "$src"' EXIT

echo "Fetching livefs-editor"
git clone https://github.com/mwhudson/livefs-editor "$src"

echo "Installing livefs-editor into $venv"
"$venv/bin/pip" install "$src"

echo "Done. livefs-edit is at $venv/bin/livefs-edit"
