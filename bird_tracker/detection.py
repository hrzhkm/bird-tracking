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

        if label != "bird" or confidence <= config.CONF_THRESH:
            roi.remove_object(detection)
            continue

        bbox = detection.get_bbox()
        center_x = bbox.xmin() + bbox.width() / 2.0
        center_y = bbox.ymin() + bbox.height() / 2.0
        track_objects = detection.get_objects_typed(hailo.HAILO_UNIQUE_ID)
        track_id = (
            track_objects[0].get_id()
            if len(track_objects) == 1
            else None
        )
        birds.append((center_x, center_y, bbox, confidence, track_id))

    tracked = None
    recovery_target = None
    if birds:
        matching_track = [
            bird
            for bird in birds
            if (
                user_data.active_track_id is not None
                and bird[4] == user_data.active_track_id
            )
        ]
        candidates = matching_track or birds
        tracked = min(
            candidates,
            key=lambda bird: (
                (bird[0] - user_data.aim_x) ** 2
                + (bird[1] - user_data.aim_y) ** 2
            ),
        )
        center_x, center_y, bbox, confidence, track_id = tracked
        now = time.monotonic()
        previous_recovery = user_data.recovery_mode
        user_data.target_predictor.observe(
            center_x,
            center_y,
            now,
            identity=track_id,
        )
        user_data.active_track_id = track_id
        user_data.recovery_mode = None
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
            user_data.last_bird_time = now
            user_data.new_frame = True
        if previous_recovery is not None:
            print(f"[BIRD] Target reacquired ({confidence:.2f})")
        elif not was_present:
            print(f"[BIRD] Target acquired ({confidence:.2f})")
    else:
        now = time.monotonic()
        prediction = user_data.target_predictor.predict(now)
        previous_recovery = user_data.recovery_mode
        with user_data.lock:
            was_present = user_data.bird_present
            last_seen = user_data.last_bird_time
            holding_detection = now - last_seen <= config.DETECTION_HOLD
            if prediction is not None:
                error_x, error_y, recovery_mode = prediction
                user_data.target_error_x = error_x
                user_data.target_error_y = error_y
                user_data.bird_present = True
                user_data.new_frame = True
            else:
                recovery_mode = None
                user_data.bird_present = holding_detection
                if previous_recovery is not None and not holding_detection:
                    user_data.stop_tracking = True

        user_data.recovery_mode = recovery_mode
        if prediction is not None:
            recovery_target = error_x + 0.5, error_y + 0.5
            user_data.aim_x = max(0.0, min(1.0, recovery_target[0]))
            user_data.aim_y = max(0.0, min(1.0, recovery_target[1]))
            if recovery_mode != previous_recovery:
                print(f"[BIRD] Recovery: {recovery_mode}")

        # Preserve the last box for display while the controller follows the
        # separately bounded predicted target.
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
        elif prediction is None and was_present:
            print("[BIRD] Target lost")

        if now - last_seen > config.HOME_TIMEOUT:
            user_data.aim_x, user_data.aim_y = 0.5, 0.5
            user_data.active_track_id = None
            user_data.target_predictor.reset()

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
        elif recovery_target is not None:
            target_x = int(
                max(0.0, min(1.0, recovery_target[0])) * width
            )
            target_y = int(
                max(0.0, min(1.0, recovery_target[1])) * height
            )
            cv2.circle(frame, (target_x, target_y), 8, (0, 165, 255), -1)
            cv2.line(
                frame,
                (width // 2, height // 2),
                (target_x, target_y),
                (0, 165, 255),
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
        if user_data.recovery_mode is not None:
            cv2.putText(
                frame,
                f"Recovery: {user_data.recovery_mode}",
                (10, 90),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 165, 255),
                2,
            )

        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        user_data.set_frame(frame)

    return Gst.PadProbeReturn.OK
