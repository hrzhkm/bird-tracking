"""Runtime tuning values for detection and servo tracking."""

import os


# Video input. "usb" asks the Hailo pipeline to discover a USB camera.
VIDEO_SOURCE = os.environ.get("BIRD_VIDEO_SOURCE", "usb")
VIDEO_SINK = os.environ.get("BIRD_VIDEO_SINK", "ximagesink")
FRAME_RATE = int(os.environ.get("BIRD_FRAME_RATE", "30"))
HEF_PATH = os.environ.get(
    "BIRD_HEF_PATH",
    "/usr/local/hailo/resources/models/hailo8/yolov6n.hef",
)
LABELS_JSON = os.environ.get("BIRD_LABELS_JSON")

if FRAME_RATE <= 0:
    raise ValueError("BIRD_FRAME_RATE must be greater than zero")

# Serial controller
SERIAL_PORT = os.environ.get("BIRD_SERVO_PORT")
SERVO_ENABLED = os.environ.get("BIRD_SERVO_ENABLED", "1") == "1"
SERIAL_BAUD = 115200
SERVO_RESYNC_IDLE = float(
    os.environ.get("BIRD_SERVO_RESYNC_IDLE", "2.5")
)
SERVO_RESYNC_SETTLE = float(
    os.environ.get("BIRD_SERVO_RESYNC_SETTLE", "0.5")
)

if SERVO_RESYNC_IDLE <= 0 or SERVO_RESYNC_SETTLE < 0:
    raise ValueError(
        "BIRD_SERVO_RESYNC_IDLE must be positive and "
        "BIRD_SERVO_RESYNC_SETTLE cannot be negative"
    )

# Image X increases to the right and image Y increases downward. On the current
# pan/tilt bracket, increasing the pan angle turns right and increasing the
# tilt angle points down.
PAN_SIGN = int(os.environ.get("BIRD_PAN_SIGN", "1"))
TILT_SIGN = int(os.environ.get("BIRD_TILT_SIGN", "1"))

if PAN_SIGN not in (-1, 1) or TILT_SIGN not in (-1, 1):
    raise ValueError("BIRD_PAN_SIGN and BIRD_TILT_SIGN must be either -1 or 1")

# Tracking controller. Speeds are degrees per second and image errors are
# normalized to -0.5..+0.5.
TARGET_FILTER_TAU = float(os.environ.get("BIRD_TARGET_FILTER_TAU", "0.02"))
DEADZONE_ENTER = float(os.environ.get("BIRD_DEADZONE_ENTER", "0.02"))
DEADZONE_EXIT = float(os.environ.get("BIRD_DEADZONE_EXIT", "0.01"))
TRACK_GAIN = float(os.environ.get("BIRD_TRACK_GAIN", "130.0"))
PRECISION_GAIN = float(os.environ.get("BIRD_PRECISION_GAIN", "20.0"))
PRECISION_ZONE = float(os.environ.get("BIRD_PRECISION_ZONE", "0.25"))
MAX_TARGET_SPEED = float(os.environ.get("BIRD_MAX_TARGET_SPEED", "30.0"))
MAX_CONTROL_DT = 0.10
CONTROL_DT = 0.02
HOME_TIMEOUT = 5.0
STARTUP_HOME_DURATION = 2.0
STARTUP_HOME_INTERVAL = 0.25

if TARGET_FILTER_TAU < 0:
    raise ValueError("BIRD_TARGET_FILTER_TAU cannot be negative")
if not 0 <= DEADZONE_EXIT < DEADZONE_ENTER <= 0.5:
    raise ValueError(
        "dead zones must satisfy 0 <= BIRD_DEADZONE_EXIT "
        "< BIRD_DEADZONE_ENTER <= 0.5"
    )
if min(TRACK_GAIN, PRECISION_GAIN, MAX_TARGET_SPEED) <= 0:
    raise ValueError(
        "tracking gains and BIRD_MAX_TARGET_SPEED must be greater than zero"
    )
if not 0 < PRECISION_ZONE <= 0.5:
    raise ValueError("BIRD_PRECISION_ZONE must be in (0, 0.5]")

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

# Detection. The custom model can drive the arm for birds and monkeys, while
# humans remain visible but are never tracking targets.
TARGET_LABELS = tuple(
    label.strip()
    for label in os.environ.get("BIRD_TARGET_LABELS", "bird,monkey").split(",")
    if label.strip()
)
CONF_THRESH = float(os.environ.get("BIRD_CONFIDENCE", "0.20"))
DETECTION_HOLD = float(os.environ.get("BIRD_DETECTION_HOLD", "1.0"))
DETECTION_DEBUG = os.environ.get("BIRD_DETECTION_DEBUG", "0") == "1"

if not TARGET_LABELS:
    raise ValueError("BIRD_TARGET_LABELS must contain at least one label")

# Lost-target recovery. Screen velocities use normalized frame units/second.
PREDICTION_VELOCITY_TAU = float(
    os.environ.get("BIRD_PREDICTION_VELOCITY_TAU", "0.15")
)
PREDICTION_COAST = float(os.environ.get("BIRD_PREDICTION_COAST", "0.60"))
PREDICTION_SEARCH = float(os.environ.get("BIRD_PREDICTION_SEARCH", "1.20"))
PREDICTION_MIN_SPEED = float(
    os.environ.get("BIRD_PREDICTION_MIN_SPEED", "0.12")
)
PREDICTION_MAX_SPEED = float(
    os.environ.get("BIRD_PREDICTION_MAX_SPEED", "2.0")
)
PREDICTION_EDGE_ZONE = float(
    os.environ.get("BIRD_PREDICTION_EDGE_ZONE", "0.20")
)
PREDICTION_SEARCH_ERROR = float(
    os.environ.get("BIRD_PREDICTION_SEARCH_ERROR", "0.30")
)
PREDICTION_MARGIN = float(os.environ.get("BIRD_PREDICTION_MARGIN", "0.20"))

# Hailo metadata tracker. This bridges short YOLO misses and keeps the target
# identity stable while the camera is moving. Inference itself still runs on
# the Hailo-8; the tracker operates on the resulting detection metadata.
TRACKER_KEEP_NEW_FRAMES = int(os.environ.get("BIRD_TRACKER_KEEP_NEW_FRAMES", "3"))
TRACKER_KEEP_TRACKED_FRAMES = int(
    os.environ.get("BIRD_TRACKER_KEEP_TRACKED_FRAMES", "10")
)
TRACKER_KEEP_LOST_FRAMES = int(
    os.environ.get("BIRD_TRACKER_KEEP_LOST_FRAMES", "4")
)

if DETECTION_HOLD < 0:
    raise ValueError("BIRD_DETECTION_HOLD cannot be negative")

if min(
    PREDICTION_VELOCITY_TAU,
    PREDICTION_COAST,
    PREDICTION_SEARCH,
    PREDICTION_MIN_SPEED,
    PREDICTION_MAX_SPEED,
) < 0:
    raise ValueError("bird prediction timing and speed values cannot be negative")
if not 0 < PREDICTION_EDGE_ZONE < 0.5:
    raise ValueError("BIRD_PREDICTION_EDGE_ZONE must be between 0 and 0.5")
if not 0 < PREDICTION_SEARCH_ERROR <= 0.5:
    raise ValueError("BIRD_PREDICTION_SEARCH_ERROR must be in (0, 0.5]")
if not 0 <= PREDICTION_MARGIN <= 0.5:
    raise ValueError("BIRD_PREDICTION_MARGIN must be between 0 and 0.5")
if PREDICTION_MAX_SPEED < PREDICTION_MIN_SPEED:
    raise ValueError(
        "BIRD_PREDICTION_MAX_SPEED must be at least BIRD_PREDICTION_MIN_SPEED"
    )

if min(
    TRACKER_KEEP_NEW_FRAMES,
    TRACKER_KEEP_TRACKED_FRAMES,
    TRACKER_KEEP_LOST_FRAMES,
) < 0:
    raise ValueError("BIRD tracker frame counts cannot be negative")
