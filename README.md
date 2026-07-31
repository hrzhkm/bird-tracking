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

USB cameras also open a small always-on-top focus panel. Drag the slider for
manual focus or enable `Auto Focus` temporarily. The last successful manual
focus value is restored from `~/.config/bird-tracker/focus` at startup.

Inference and aggregation queues remain synchronized so detection metadata is
attached to the correct video frame. Only whole frames are dropped before the
split or after aggregation when the pipeline falls behind.

`PEST_CONFIDENCE` controls the minimum pest confidence used by both Hailo
inference and the tracking callback. The default is `0.5`; increase it if the
tracker produces false detections.

`PEST_TARGET_LABELS=bird,monkey` controls which detections may move the arm.
`SERVO_ENABLED=0` disables serial movement for safe candidate testing.

Hailo's metadata tracker runs before the control callback to retain target
identity. It stops emitting a box after one unmatched frame, while lost IDs are
kept internally for reacquisition. A fresh detector miss shows only the orange
predicted aim point and coasts for at most
`LOST_TARGET_COAST_SECONDS=0.20`; larger values are capped at 200 ms so old
`.env` files remain safe. Tracking then sends an explicit stop.

At startup, `run.sh` verifies that a Hailo device is present and that its
architecture matches `hailo_arch`. It exits instead of silently attempting a
CPU-only path. Command-line options remain available and `.env` now supplies
the actual default input and frame rate without launcher overrides.

`SERVO_HOME_TILT` and `SERVO_HOME_PAN` set the home position in normal `0..180`
servo coordinates. The configured defaults are tilt `100` and pan `90`. Values
must remain within the ESP32 joint limits: pan `10..170`, tilt `35..135`.
`SERVO_PAN_SIGN` and `SERVO_TILT_SIGN` control the tracking direction for each
axis and must be `1` or `-1`. Image Y and the tilt servo angle both increase
in opposite directions on this bracket, so the default tilt sign is `-1`.

Movement smoothing can be tuned in `.env`. `TRACKING_FILTER_TAU=0.08`
filters detection noise, while `TRACKING_DEADZONE_ENTER=0.01` and
`TRACKING_DEADZONE_EXIT=0.004` stop movement close to the image center.
`TRACKING_PAN_GAIN=80`, `TRACKING_TILT_GAIN=60`, and
`TRACKING_MAX_SPEED=45` control the continuous tracking speed.
`TRACKING_FAR_BOOST=2` smoothly adds speed while the target is far from center
without changing the base response at center. Use max speed/boost `40/1.5` for
conservative tracking, `45/2` for balanced tracking, or `60/4` for aggressive
tracking.
`TRACKING_LOOKAHEAD=0.14` projects the measured screen motion forward to
compensate for camera and inference delay. Increase it if the camera crosses
the target before braking; reduce it if the camera consistently stops short.
`TRACKING_MAX_FRAME_AGE=0.25` prevents camera frames older than 250 ms from
commanding the servos. Rejected frames print a rate-limited `[LATENCY]` warning.
Live tracking uses `V,pan_speed,tilt_speed` commands. The ESP32 applies the
acceleration limit and stops a stale velocity command automatically. Absolute
`pan,tilt` commands remain in use for startup and homing.

For latency diagnosis, start with `HAILO_MONITOR=1 ./run.sh --show-fps`, then
run `hailortcli monitor` in another terminal. Use `htop` for host load and
`vcgencmd get_throttled && vcgencmd measure_temp` for Raspberry Pi power and
thermal status.

The tracker automatically selects an ESP32 with a CP2102 USB adapter and will
not fall back to unrelated serial devices. Restart `run.sh` after reconnecting
the USB cable. For another adapter, set its stable USB ID:

```bash
SERVO_PORT=/dev/serial/by-id/your-device
```

Tracking and servo tuning values are in `bird_tracker/config.py`.
