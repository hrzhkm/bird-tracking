"""Hailo buffer callback and bird target selection."""

import time

import cv2
import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst

import hailo
from hailo_apps.hailo_app_python.core.common.buffer_utils import (
    get_caps_from_pad,
    get_numpy_from_buffer,
)

from . import config


def app_callback(pad, info, user_data):
    buffer = info.get_buffer()
    if buffer is None:
        return Gst.PadProbeReturn.OK

    user_data.increment()
    frame_format, width, height = get_caps_from_pad(pad)

    frame = None
    if user_data.use_frame:
        frame = get_numpy_from_buffer(buffer, frame_format, width, height)

    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)

    birds = []
    for detection in detections:
        label = detection.get_label()
        confidence = detection.get_confidence()

        if label == "bird" and confidence > config.CONF_THRESH:
            bbox = detection.get_bbox()
            center_x = bbox.xmin() + bbox.width() / 2.0
            center_y = bbox.ymin() + bbox.height() / 2.0
            birds.append((center_x, center_y))
        else:
            roi.remove_object(detection)

    tracked = None
    if birds:
        tracked = min(
            birds,
            key=lambda bird: (
                (bird[0] - user_data.aim_x) ** 2
                + (bird[1] - user_data.aim_y) ** 2
            ),
        )
        center_x, center_y = tracked
        user_data.aim_x, user_data.aim_y = center_x, center_y
        with user_data.lock:
            user_data.target_error_x = center_x - 0.5
            user_data.target_error_y = center_y - 0.5
            user_data.bird_present = True
            user_data.last_bird_time = time.time()
            user_data.new_frame = True
    else:
        now = time.time()
        with user_data.lock:
            user_data.bird_present = False
            last_seen = user_data.last_bird_time
        if now - last_seen > config.HOME_TIMEOUT:
            user_data.aim_x, user_data.aim_y = 0.5, 0.5

    if user_data.use_frame:
        cv2.drawMarker(
            frame,
            (width // 2, height // 2),
            (0, 255, 255),
            cv2.MARKER_CROSS,
            20,
            1,
        )

        if tracked is not None:
            target_x = int(tracked[0] * width)
            target_y = int(tracked[1] * height)
            cv2.circle(frame, (target_x, target_y), 8, (0, 0, 255), -1)
            cv2.line(
                frame,
                (width // 2, height // 2),
                (target_x, target_y),
                (0, 0, 255),
                1,
            )

        cv2.putText(
            frame,
            f"Birds: {len(birds)}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
        )
        cv2.putText(
            frame,
            f"Pan: {user_data.pan_angle:+.0f}  Tilt: {user_data.tilt_angle:+.0f}",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )

        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        user_data.set_frame(frame)

    return Gst.PadProbeReturn.OK

