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
`BIRD_FRAME_RATE=20` limits inference and DMA pressure on the Raspberry Pi.

`BIRD_CONFIDENCE` controls the minimum bird confidence used by both Hailo
inference and the tracking callback. The default is `0.20`; increase it if the
tracker produces false bird detections.

`BIRD_DETECTION_HOLD=1.0` keeps the most recent valid bird box visible across
brief inference misses without moving the servos from stale coordinates.

`BIRD_HOME_TILT` and `BIRD_HOME_PAN` set the home position in normal `0..180`
servo coordinates. The configured defaults are tilt `80` and pan `70`. Values
must remain within the ESP32 joint limits: pan `10..170`, tilt `20..120`.

You can also select the servo controller there, preferably using its stable USB
ID:

```bash
BIRD_SERVO_PORT=/dev/serial/by-id/your-device
```

Tracking and servo tuning values are in `bird_tracker/config.py`.
