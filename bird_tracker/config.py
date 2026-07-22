"""Runtime tuning values for detection and servo tracking."""

import os


# Video input. "usb" asks the Hailo pipeline to discover a USB camera.
VIDEO_SOURCE = os.environ.get("BIRD_VIDEO_SOURCE", "usb")

# Serial controller
SERIAL_PORT = os.environ.get("BIRD_SERVO_PORT")
SERIAL_BAUD = 115200

# Flip either sign if that servo moves in the wrong direction.
PAN_SIGN = 1
TILT_SIGN = 1

# Tracking controller
KP = 7.0
MAX_STEP = 1.5
DEADZONE = 0.05
CONTROL_DT = 0.02
HOME_TIMEOUT = 5.0

# Angles use an internal -90..+90 convention, where 0 is centered.
PAN_MIN, PAN_MAX = -90, 90
TILT_MIN, TILT_MAX = -90, 90

# Detection. Hailo's COCO label table uses class ID 15 for "bird".
BIRD_CLASS_ID = 15
CONF_THRESH = float(os.environ.get("BIRD_CONFIDENCE", "0.20"))
