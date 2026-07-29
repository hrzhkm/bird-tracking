#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
host="${BIRD_TRACKER_HOST:-pi@100.80.235.77}"
remote_dir="${BIRD_TRACKER_REMOTE_DIR:-/home/pi/bird-tracker}"

mkdir -p "$root/dataset"
ssh -o BatchMode=yes "$host" "test -d '$remote_dir/dataset'" || {
  echo "No dataset found on $host; run script/collect-dataset.sh there first." >&2
  exit 1
}
rsync -ah --info=progress2 -e "ssh -o BatchMode=yes" \
  "$host:$remote_dir/dataset/" "$root/dataset/"
