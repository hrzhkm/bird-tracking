#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
device="${1:-/dev/video0}"
output="$root/dataset/$(date +%Y-%m-%d_%H-%M-%S).mkv"

mkdir -p "$root/dataset"
echo "Recording $device to $output (press Ctrl+C to stop)"
exec ffmpeg -hide_banner -f v4l2 -input_format mjpeg -framerate 30 \
  -video_size 640x480 -i "$device" -c:v copy "$output"
