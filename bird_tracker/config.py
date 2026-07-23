"""Runtime tuning values for detection and servo tracking."""

import os


# Video input. "usb" asks the Hailo pipeline to discover a USB camera.
VIDEO_SOURCE = os.environ.get("BIRD_VIDEO_SOURCE", "usb")
VIDEO_SINK = os.environ.get("BIRD_VIDEO_SINK", "ximagesink")
FRAME_RATE = int(os.environ.get("BIRD_FRAME_RATE", "20"))

if FRAME_RATE <= 0:
    raise ValueError("BIRD_FRAME_RATE must be greater than zero")

# Serial controller
SERIAL_PORT = os.environ.get("BIRD_SERVO_PORT")
SERIAL_BAUD = 115200

# Image X increases to the right and image Y increases downward. On the current
# pan/tilt bracket, increasing the pan angle turns right while decreasing the
# tilt angle points down.
PAN_SIGN = int(os.environ.get("BIRD_PAN_SIGN", "1"))
TILT_SIGN = int(os.environ.get("BIRD_TILT_SIGN", "-1"))

if PAN_SIGN not in (-1, 1) or TILT_SIGN not in (-1, 1):
    raise ValueError("BIRD_PAN_SIGN and BIRD_TILT_SIGN must be either -1 or 1")

# Tracking controller
KP = 7.0
MAX_STEP = 1.5
DEADZONE = 0.05
CONTROL_DT = 0.02
HOME_TIMEOUT = 5.0
STARTUP_HOME_DURATION = 2.0
STARTUP_HOME_INTERVAL = 0.25

# Physical limits enforced by the ESP32, expressed in normal servo coordinates.
PAN_SERVO_MIN, PAN_SERVO_MAX = 10, 170
TILT_SERVO_MIN, TILT_SERVO_MAX = 20, 120

# The Python controller uses -90..+90 internally, where 0 is servo position 90.
PAN_MIN, PAN_MAX = PAN_SERVO_MIN - 90, PAN_SERVO_MAX - 90
TILT_MIN, TILT_MAX = TILT_SERVO_MIN - 90, TILT_SERVO_MAX - 90

# Home values in .env use normal 0..180 servo coordinates. Convert them to
# the controller's internal -90..+90 coordinates here.
HOME_PAN = float(os.environ.get("BIRD_HOME_PAN", "70")) - 90.0
HOME_TILT = float(os.environ.get("BIRD_HOME_TILT", "80")) - 90.0

if not PAN_MIN <= HOME_PAN <= PAN_MAX:
    raise ValueError(
        f"BIRD_HOME_PAN must be between {PAN_SERVO_MIN} and {PAN_SERVO_MAX}"
    )
if not TILT_MIN <= HOME_TILT <= TILT_MAX:
    raise ValueError(
        f"BIRD_HOME_TILT must be between {TILT_SERVO_MIN} and {TILT_SERVO_MAX}"
    )

# Detection. Hailo's COCO label table uses class ID 15 for "bird".
BIRD_CLASS_ID = 15
CONF_THRESH = float(os.environ.get("BIRD_CONFIDENCE", "0.20"))
DETECTION_HOLD = float(os.environ.get("BIRD_DETECTION_HOLD", "1.0"))
DETECTION_DEBUG = os.environ.get("BIRD_DETECTION_DEBUG", "0") == "1"

# Hailo metadata tracker. This bridges short YOLO misses and keeps the target
# identity stable while the camera is moving. Inference itself still runs on
# the Hailo-8; the tracker operates on the resulting detection metadata.
TRACKER_KEEP_NEW_FRAMES = int(os.environ.get("BIRD_TRACKER_KEEP_NEW_FRAMES", "3"))
TRACKER_KEEP_TRACKED_FRAMES = int(
    os.environ.get("BIRD_TRACKER_KEEP_TRACKED_FRAMES", "40")
)
TRACKER_KEEP_LOST_FRAMES = int(
    os.environ.get("BIRD_TRACKER_KEEP_LOST_FRAMES", "10")
)

if DETECTION_HOLD < 0:
    raise ValueError("BIRD_DETECTION_HOLD cannot be negative")

if min(
    TRACKER_KEEP_NEW_FRAMES,
    TRACKER_KEEP_TRACKED_FRAMES,
    TRACKER_KEEP_LOST_FRAMES,
) < 0:
    raise ValueError("BIRD tracker frame counts cannot be negative")
