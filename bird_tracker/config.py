"""Runtime tuning values for detection and servo tracking."""

import os


FALLBACK_MODEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "models", "v0.0.4"
)

# Video input. "usb" asks the Hailo pipeline to discover a USB camera.
VIDEO_SOURCE = os.environ.get("VIDEO_SOURCE", "usb")
VIDEO_SINK = os.environ.get("VIDEO_SINK", "ximagesink")
FRAME_RATE = int(os.environ.get("VIDEO_FRAME_RATE", "30"))
HEF_PATH = os.environ.get(
    "MODEL_HEF_PATH",
    os.path.join(FALLBACK_MODEL_DIR, "model.hef"),
)
LABELS_JSON = os.environ.get(
    "MODEL_LABELS_JSON",
    os.path.join(FALLBACK_MODEL_DIR, "labels.json"),
)
MODEL_VERSION = os.environ.get(
    "MODEL_VERSION",
    os.path.basename(HEF_PATH),
)

if FRAME_RATE <= 0:
    raise ValueError("VIDEO_FRAME_RATE must be greater than zero")

# Serial controller
SERIAL_PORT = os.environ.get("SERVO_PORT")
SERVO_ENABLED = os.environ.get("SERVO_ENABLED", "1") == "1"
SERIAL_BAUD = 115200

# Image X increases to the right and image Y increases downward. On the current
# pan/tilt bracket, increasing the pan angle turns right while decreasing the
# tilt angle points down.
PAN_SIGN = int(os.environ.get("SERVO_PAN_SIGN", "1"))
TILT_SIGN = int(os.environ.get("SERVO_TILT_SIGN", "-1"))

if PAN_SIGN not in (-1, 1) or TILT_SIGN not in (-1, 1):
    raise ValueError("SERVO_PAN_SIGN and SERVO_TILT_SIGN must be either -1 or 1")

# Tracking controller. Speeds are degrees per second and image errors are
# normalized to -0.5..+0.5.
TARGET_FILTER_TAU = float(os.environ.get("TRACKING_FILTER_TAU", "0.08"))
DEADZONE_ENTER = float(os.environ.get("TRACKING_DEADZONE_ENTER", "0.01"))
DEADZONE_EXIT = float(os.environ.get("TRACKING_DEADZONE_EXIT", "0.004"))
PAN_TRACK_GAIN = float(os.environ.get("TRACKING_PAN_GAIN", "80.0"))
TILT_TRACK_GAIN = float(os.environ.get("TRACKING_TILT_GAIN", "60.0"))
MAX_TARGET_SPEED = float(os.environ.get("TRACKING_MAX_SPEED", "45.0"))
FAR_BOOST = float(os.environ.get("TRACKING_FAR_BOOST", "2.0"))
CONTROL_LOOKAHEAD = float(
    os.environ.get("TRACKING_LOOKAHEAD", "0.14")
)
MAX_FRAME_AGE = float(os.environ.get("TRACKING_MAX_FRAME_AGE", "0.25"))
MAX_CONTROL_DT = 0.10
CONTROL_DT = 0.02
HOME_TIMEOUT = 5.0
STARTUP_HOME_DURATION = 2.0
STARTUP_HOME_INTERVAL = 0.25

if TARGET_FILTER_TAU < 0:
    raise ValueError("TRACKING_FILTER_TAU cannot be negative")
if not 0 <= DEADZONE_EXIT < DEADZONE_ENTER <= 0.5:
    raise ValueError(
        "dead zones must satisfy 0 <= TRACKING_DEADZONE_EXIT "
        "< TRACKING_DEADZONE_ENTER <= 0.5"
    )
if min(PAN_TRACK_GAIN, TILT_TRACK_GAIN, MAX_TARGET_SPEED) <= 0:
    raise ValueError(
        "tracking gains and TRACKING_MAX_SPEED must be greater than zero"
    )
if MAX_TARGET_SPEED > 60:
    raise ValueError("TRACKING_MAX_SPEED cannot exceed 60")
if FAR_BOOST < 0:
    raise ValueError("TRACKING_FAR_BOOST cannot be negative")
if CONTROL_LOOKAHEAD < 0:
    raise ValueError("TRACKING_LOOKAHEAD cannot be negative")
if MAX_FRAME_AGE <= 0:
    raise ValueError("TRACKING_MAX_FRAME_AGE must be greater than zero")

# Physical limits enforced by the ESP32, expressed in normal servo coordinates.
PAN_SERVO_MIN, PAN_SERVO_MAX = 10, 170
TILT_SERVO_MIN, TILT_SERVO_MAX = 35, 135

# The Python controller uses -90..+90 internally, where 0 is servo position 90.
PAN_MIN, PAN_MAX = PAN_SERVO_MIN - 90, PAN_SERVO_MAX - 90
TILT_MIN, TILT_MAX = TILT_SERVO_MIN - 90, TILT_SERVO_MAX - 90

# Home values in .env use normal 0..180 servo coordinates. Convert them to
# the controller's internal -90..+90 coordinates here.
HOME_PAN = float(os.environ.get("SERVO_HOME_PAN", "90")) - 90.0
HOME_TILT = float(os.environ.get("SERVO_HOME_TILT", "100")) - 90.0

if not PAN_MIN <= HOME_PAN <= PAN_MAX:
    raise ValueError(
        f"SERVO_HOME_PAN must be between {PAN_SERVO_MIN} and {PAN_SERVO_MAX}"
    )
if not TILT_MIN <= HOME_TILT <= TILT_MAX:
    raise ValueError(
        f"SERVO_HOME_TILT must be between {TILT_SERVO_MIN} and {TILT_SERVO_MAX}"
    )

# Detection. The custom model can drive the arm for birds and monkeys, while
# humans remain visible but are never tracking targets.
TARGET_LABELS = tuple(
    label.strip()
    for label in os.environ.get("PEST_TARGET_LABELS", "bird,monkey").split(",")
    if label.strip()
)
CONF_THRESH = float(os.environ.get("PEST_CONFIDENCE", "0.5"))
DETECTION_DEBUG = os.environ.get("PEST_DETECTION_DEBUG", "0") == "1"

if not TARGET_LABELS:
    raise ValueError("PEST_TARGET_LABELS must contain at least one label")

# Lost-target recovery. Screen velocities use normalized frame units/second.
PREDICTION_VELOCITY_TAU = float(
    os.environ.get("LOST_TARGET_VELOCITY_TAU", "0.15")
)
PREDICTION_COAST = min(
    float(os.environ.get("LOST_TARGET_COAST_SECONDS", "0.20")),
    0.20,
)
PREDICTION_MIN_SPEED = float(
    os.environ.get("LOST_TARGET_MIN_SPEED", "0.12")
)
PREDICTION_MAX_SPEED = float(
    os.environ.get("LOST_TARGET_MAX_SPEED", "2.0")
)
PREDICTION_MARGIN = float(os.environ.get("LOST_TARGET_MARGIN", "0.20"))

# Keep target identity across misses without emitting unmatched predicted boxes.
TRACKER_KEEP_NEW_FRAMES = int(os.environ.get("HAILO_TRACKER_KEEP_NEW_FRAMES", "3"))
TRACKER_KEEP_TRACKED_FRAMES = 1
TRACKER_KEEP_LOST_FRAMES = int(
    os.environ.get("HAILO_TRACKER_KEEP_LOST_FRAMES", "30")
)

if min(
    PREDICTION_VELOCITY_TAU,
    PREDICTION_COAST,
    PREDICTION_MIN_SPEED,
    PREDICTION_MAX_SPEED,
) < 0:
    raise ValueError("lost-target timing and speed values cannot be negative")
if not 0 <= PREDICTION_MARGIN <= 0.5:
    raise ValueError("LOST_TARGET_MARGIN must be between 0 and 0.5")
if PREDICTION_MAX_SPEED < PREDICTION_MIN_SPEED:
    raise ValueError(
        "LOST_TARGET_MAX_SPEED must be at least LOST_TARGET_MIN_SPEED"
    )

if min(
    TRACKER_KEEP_NEW_FRAMES,
    TRACKER_KEEP_TRACKED_FRAMES,
    TRACKER_KEEP_LOST_FRAMES,
) < 0:
    raise ValueError("Hailo tracker frame counts cannot be negative")
