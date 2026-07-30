# Bird Tracker

Bird and monkey detection with pan/tilt tracking for the Raspberry Pi 5 and
Hailo pipeline. Human detections never become arm targets.

## Run

Create the local configuration once after cloning:

```bash
cp .env.example .env
```

Review `.env`, especially `hailo_arch` and the installed Hailo version values.
`VIDEO_SOURCE=usb` automatically selects an attached USB camera. Then
start the tracker:

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
`MODEL_HEF_PATH` fallback. The selected slot and model version are displayed in
the bottom-left corner of the video.

The launcher reads `.env` from this directory and can be called from anywhere.
Relative paths in `.env` are resolved from the `bird-tracker` directory. The
default configuration expects a sibling `hailo-rpi5-examples` checkout and its
`venv` Python environment.

You can replace `VIDEO_SOURCE=usb` with a specific device such as
`/dev/video0`. A command-line `--input` argument overrides the `.env` value for
one run.

`VIDEO_SINK=ximagesink` provides a stable X11/VNC display path.
`VIDEO_FRAME_RATE=30` matches the maximum 640x480 rate of the current USB
camera. `MODEL_HEF_PATH` and `MODEL_LABELS_JSON` select the known-good custom
`v0.0.4` Hailo-8 release when no production model is installed. Candidate and
production slots override both paths. Motion speed is tuned independently
below.
Inference and aggregation queues remain synchronized so detection metadata is
attached to the correct video frame; do not make those queues independently
leaky.

`PEST_CONFIDENCE` controls the minimum pest confidence used by both Hailo
inference and the tracking callback. The default is `0.5`; increase it if the
tracker produces false detections.

`PEST_TARGET_LABELS=bird,monkey` controls which detections may move the arm.
`SERVO_ENABLED=0` disables serial movement for safe candidate testing.

`PEST_DETECTION_HOLD=1.0` keeps the most recent valid target box visible across
brief inference misses without moving the servos from stale coordinates.

Hailo's metadata tracker runs before the control callback, so its Kalman
prediction bridges detector misses while retaining the active target ID. The
default 60 tracked plus 30 lost frames cover about three seconds at 30 FPS.
While that ID is locked, another animal cannot take over merely because it is
closer. Bounded lost-target recovery extrapolates recent screen velocity for
0.6 seconds, then searches toward a likely exit edge for at most 1.2 seconds.
A weak or non-edge-directed motion estimate stops instead of initiating a
blind search. Tune the `HAILO_TRACKER_*` and `LOST_TARGET_*` values in
`.env` if necessary.

At startup, `run.sh` verifies that a Hailo device is present and that its
architecture matches `hailo_arch`. It exits instead of silently attempting a
CPU-only path. Command-line options remain available and `.env` now supplies
the actual default input and frame rate without launcher overrides.

`SERVO_HOME_TILT` and `SERVO_HOME_PAN` set the home position in normal `0..180`
servo coordinates. The configured defaults are tilt `100` and pan `90`. Values
must remain within the ESP32 joint limits: pan `10..170`, tilt `35..135`.
`SERVO_PAN_SIGN` and `SERVO_TILT_SIGN` control the tracking direction for each
axis and must be `1` or `-1`. Image Y and the tilt servo angle both increase
downward on this bracket, so the default tilt sign is `1`.

Movement smoothing can be tuned in `.env`. `TRACKING_FILTER_TAU=0.08`
filters detection noise, while `TRACKING_DEADZONE_ENTER=0.01` and
`TRACKING_DEADZONE_EXIT=0.004` stop movement close to the image center.
`TRACKING_PAN_GAIN=80`, `TRACKING_TILT_GAIN=60`, and
`TRACKING_MAX_SPEED=30` control the continuous tracking speed.
`TRACKING_LOOKAHEAD=0.14` projects the measured screen motion forward to
compensate for camera and inference delay. Increase it if the camera crosses
the target before braking; reduce it if the camera consistently stops short.
Live tracking uses `V,pan_speed,tilt_speed` commands. The ESP32 applies the
acceleration limit and stops a stale velocity command automatically. Absolute
`pan,tilt` commands remain in use for startup and homing.

The tracker automatically selects an ESP32 with a CP2102 USB adapter and will
not fall back to unrelated serial devices. Restart `run.sh` after reconnecting
the USB cable. For another adapter, set its stable USB ID:

```bash
SERVO_PORT=/dev/serial/by-id/your-device
```

Tracking and servo tuning values are in `bird_tracker/config.py`.
