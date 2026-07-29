#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
device="${1:-/dev/video0}"
output="$root/dataset/$(date +%Y-%m-%d_%H-%M-%S).mkv"

mkdir -p "$root/dataset"

if [[ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" && -S "/run/user/$(id -u)/wayland-0" ]]; then
  export XDG_RUNTIME_DIR="/run/user/$(id -u)"
  export WAYLAND_DISPLAY=wayland-0
fi

echo "Recording $device to $output with live preview (press Ctrl+C to stop)"
exec ffmpeg -hide_banner -f v4l2 -input_format mjpeg -framerate 30 \
  -video_size 640x480 -i "$device" \
  -map 0:v -c:v copy "$output" \
  -map 0:v -vf format=yuv420p -f sdl "Camera Preview"
