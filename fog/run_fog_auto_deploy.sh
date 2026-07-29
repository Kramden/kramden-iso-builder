#!/bin/bash
set -euo pipefail

cd /root/kramden-iso-builder/fog
source /root/kramden-iso-builder/fog/env.sh

exec python3 /root/kramden-iso-builder/fog/fog_auto_deploy.py
