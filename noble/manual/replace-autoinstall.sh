#!/bin/bash
#
# Takes an existing Kramden desktop ISO and replaces the autoinstall.yaml at
# its root with the one next to this script (e.g. after tweaking
# interactive-sections), without needing a full CI rebuild.
#
# Requires the venv set up by setup-livefs-editor-venv.sh in this directory.
set -euo pipefail

dir=$(dirname $(realpath $0))
livefs_edit=$dir/venv/bin/livefs-edit

if [ $UID != 0 ];
then
	echo "Must be run with root privileges, for example with sudo"
	exit 1
fi

if [ $# -lt 2 ];
then
	echo "USAGE: sudo $0 SOURCE_ISO OUTPUT_ISO"
	exit 1
fi

source_iso=$1
output_iso=$2

if [ ! -x "$livefs_edit" ];
then
	echo "livefs-edit not found at $livefs_edit. Run $dir/setup-livefs-editor-venv.sh first." >&2
	exit 1
fi

if [ -e "$output_iso" ];
then
	echo "$output_iso already exists, refusing to overwrite" >&2
	exit 1
fi

echo "Copying $dir/autoinstall.yaml into $source_iso -> $output_iso"
"$livefs_edit" "$source_iso" "$output_iso" --cp "$dir/autoinstall.yaml" new/iso/autoinstall.yaml

echo "$output_iso created"
