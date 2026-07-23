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

    if (
        config.DETECTION_DEBUG
        and time.monotonic() - user_data.last_detection_debug_time >= 1.0
    ):
        summary = ", ".join(
            f"{detection.get_label()!r}:{detection.get_confidence():.2f}"
            for detection in detections[:10]
        )
        print(f"[DETECTIONS] {summary or 'none'}", flush=True)
        user_data.last_detection_debug_time = time.monotonic()

    birds = []
    for detection in detections:
        label = detection.get_label()
        confidence = detection.get_confidence()

        if label == "bird" and confidence > config.CONF_THRESH:
            bbox = detection.get_bbox()
            center_x = bbox.xmin() + bbox.width() / 2.0
            center_y = bbox.ymin() + bbox.height() / 2.0
            birds.append((center_x, center_y, bbox, confidence))

    tracked = None
    if birds:
        tracked = min(
            birds,
            key=lambda bird: (
                (bird[0] - user_data.aim_x) ** 2
                + (bird[1] - user_data.aim_y) ** 2
            ),
        )
        center_x, center_y, bbox, confidence = tracked
        user_data.aim_x, user_data.aim_y = center_x, center_y
        user_data.last_bird_bbox = (
            bbox.xmin(),
            bbox.ymin(),
            bbox.width(),
            bbox.height(),
        )
        user_data.last_bird_confidence = confidence
        with user_data.lock:
            was_present = user_data.bird_present
            user_data.target_error_x = center_x - 0.5
            user_data.target_error_y = center_y - 0.5
            user_data.bird_present = True
            user_data.last_bird_time = time.monotonic()
            user_data.new_frame = True
        if not was_present:
            print(f"[BIRD] Target acquired ({confidence:.2f})")
    else:
        now = time.monotonic()
        with user_data.lock:
            was_present = user_data.bird_present
            last_seen = user_data.last_bird_time
            holding_detection = now - last_seen <= config.DETECTION_HOLD
            user_data.bird_present = holding_detection

        # Preserve only the visual box during brief model misses. The control
        # thread receives no fresh-frame flag, so stale positions do not move
        # the servos.
        if holding_detection and user_data.last_bird_bbox is not None:
            xmin, ymin, box_width, box_height = user_data.last_bird_bbox
            held_bbox = hailo.HailoBBox(xmin, ymin, box_width, box_height)
            held_detection = hailo.HailoDetection(
                held_bbox,
                config.BIRD_CLASS_ID,
                "bird",
                user_data.last_bird_confidence,
            )
            roi.add_object(held_detection)
        elif was_present:
            print("[BIRD] Target lost")

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
