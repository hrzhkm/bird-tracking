# Bird Tracker

Bird detection and pan/tilt tracking for the Raspberry Pi 5 and Hailo pipeline.

## Run

Create the local configuration once after cloning:

```bash
cp .env.example .env
```

Review `.env`, especially `HAILO_EXAMPLES_DIR`, `hailo_arch`, and the installed
Hailo version values. `BIRD_VIDEO_SOURCE=usb` automatically selects an attached
USB camera. Then start the tracker:

```bash
./run.sh
```

The launcher reads `.env` from this directory and can be called from anywhere.
Relative paths in `.env` are resolved from the `bird-tracker` directory. The
default configuration expects a sibling `hailo-rpi5-examples` checkout and its
`venv` Python environment.

For a different layout, edit `.env`:

```bash
HAILO_EXAMPLES_DIR=/path/to/hailo-rpi5-examples
BIRD_TRACKER_PYTHON=/path/to/python
BIRD_VIDEO_SOURCE=usb
```

You can replace `usb` with a specific device such as `/dev/video0`. A command-line
`--input` argument overrides the `.env` value for one run.

`BIRD_VIDEO_SINK=ximagesink` provides a stable X11/VNC display path.
`BIRD_FRAME_RATE=15` avoids the sustained QoS drops observed at 20 FPS on the
current Raspberry Pi pipeline; motion speed is tuned independently below.
Inference and aggregation queues remain synchronized so detection metadata is
attached to the correct video frame; do not make those queues independently
leaky.

`BIRD_CONFIDENCE` controls the minimum bird confidence used by both Hailo
inference and the tracking callback. The default is `0.20`; increase it if the
tracker produces false bird detections.

`BIRD_DETECTION_HOLD=1.0` keeps the most recent valid bird box visible across
brief inference misses without moving the servos from stale coordinates.

After the raw detections reach the control callback, the display pipeline uses
Hailo's metadata tracker for COCO bird class 15. Its default 40-frame tracked
window bridges about 2.7 seconds of detector misses at 15 FPS; tune
`BIRD_TRACKER_KEEP_TRACKED_FRAMES` in `.env` if necessary.

At startup, `run.sh` verifies that a Hailo device is present and that its
architecture matches `hailo_arch`. It exits instead of silently attempting a
CPU-only path. Command-line options remain available and `.env` now supplies
the actual default input and frame rate without launcher overrides.

`BIRD_HOME_TILT` and `BIRD_HOME_PAN` set the home position in normal `0..180`
servo coordinates. The configured defaults are tilt `80` and pan `70`. Values
must remain within the ESP32 joint limits: pan `10..170`, tilt `20..120`.
`BIRD_PAN_SIGN` and `BIRD_TILT_SIGN` control the tracking direction for each
axis and must be `1` or `-1`. Image Y and the tilt servo angle both increase
downward on this bracket, so the default tilt sign is `1`.

Movement smoothing can be tuned in `.env`. `BIRD_TARGET_FILTER_TAU=0.05`
filters detection noise, while `BIRD_DEADZONE_ENTER=0.06` and
`BIRD_DEADZONE_EXIT=0.035` prevent repeated movement around the image center.
`BIRD_TRACK_GAIN=130` and `BIRD_MAX_TARGET_SPEED=30` control tracking response
and speed in servo degrees per second. The defaults provide balanced movement;
increase the filter time or reduce the speed for a smoother but slower response.
Live tracking uses relative `R,pan_delta,tilt_delta` commands so the ESP32 never
queues a distant target beyond the bird. Absolute `pan,tilt` commands remain in
use for startup and homing.

You can also select the servo controller there, preferably using its stable USB
ID:

```bash
BIRD_SERVO_PORT=/dev/serial/by-id/your-device
```

Tracking and servo tuning values are in `bird_tracker/config.py`.
