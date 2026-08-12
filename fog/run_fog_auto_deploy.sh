#!/bin/bash
set -euo pipefail

cd /root/kramden-iso-builder/fog
source /root/kramden-iso-builder/fog/env.sh

# Run each release as its own process so a failure in one (e.g. resolute
# not configured yet) can't prevent the other from running.
failures=0
for release in noble resolute; do
    echo "=== fog_auto_deploy: ${release} ==="
    if ! python3 /root/kramden-iso-builder/fog/fog_auto_deploy.py --release "$release"; then
        echo "=== fog_auto_deploy: ${release} FAILED ===" >&2
        failures=$((failures + 1))
    fi
done

exit "$failures"
