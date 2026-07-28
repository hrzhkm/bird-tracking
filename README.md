# Bird Tracker

Bird and monkey detection with pan/tilt tracking for the Raspberry Pi 5 and
Hailo pipeline. Human detections never become arm targets.

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

When versioned releases are installed under `models/`, the launcher provides
three model slots:

```bash
./run.sh --candidate-safe  # candidate model, servo disabled
./run.sh --candidate       # candidate model, servo enabled
./run.sh                   # approved production model
```

The candidate commands require `models/candidate` to point to a complete
release containing `model.hef` and `labels.json`. Normal startup uses
`models/production` when present and otherwise retains the configured
`BIRD_HEF_PATH` fallback. The selected slot and model version are displayed in
the bottom-left corner of the video.

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
`BIRD_FRAME_RATE=30` matches the maximum 640x480 rate of the current USB
camera. `BIRD_HEF_PATH` selects the installed YOLOv6n Hailo-8 model, which
keeps the full pipeline at 30 FPS with lower inference latency than YOLOv8m.
Motion speed is tuned independently below.
Inference and aggregation queues remain synchronized so detection metadata is
attached to the correct video frame; do not make those queues independently
leaky.

`BIRD_CONFIDENCE` controls the minimum bird confidence used by both Hailo
inference and the tracking callback. The default is `0.5`; increase it if the
tracker produces false bird detections.

`BIRD_TARGET_LABELS=bird,monkey` controls which detections may move the arm.
`BIRD_SERVO_ENABLED=0` disables serial movement for safe candidate testing.

`BIRD_DETECTION_HOLD=1.0` keeps the most recent valid bird box visible across
brief inference misses without moving the servos from stale coordinates.

Hailo's metadata tracker runs before the control callback, so its Kalman
prediction bridges detector misses while retaining the active target ID. The
default 60 tracked plus 30 lost frames cover about three seconds at 30 FPS.
While that ID is locked, another animal cannot take over merely because it is
closer. Bounded lost-target recovery extrapolates recent screen velocity for
0.6 seconds, then searches toward a likely exit edge for at most 1.2 seconds.
A weak or non-edge-directed motion estimate stops instead of initiating a
blind search. Tune the `BIRD_TRACKER_*` and `BIRD_PREDICTION_*` values in
`.env` if necessary.

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
If the ESP32 command stream has been idle for `BIRD_SERVO_RESYNC_IDLE=2.5`
seconds, the next target first reasserts the known absolute position and waits
`BIRD_SERVO_RESYNC_SETTLE=0.5` seconds. This prevents physical drift while the
servos are detached from corrupting the first relative tracking movement.

Movement smoothing can be tuned in `.env`. `BIRD_TARGET_FILTER_TAU=0.02`
filters detection noise, while `BIRD_DEADZONE_ENTER=0.02` and
`BIRD_DEADZONE_EXIT=0.01` stop movement close to the image center.
`BIRD_TRACK_GAIN=130` and `BIRD_MAX_TARGET_SPEED=30` provide fast travel;
inside `BIRD_PRECISION_ZONE=0.25`, `BIRD_PRECISION_GAIN=20` brakes for accurate
centering. These values control tracking response
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
