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
from .motion import frame_age_seconds, frame_is_fresh, predict_error
from .targeting import choose_target, is_tracking_target


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

    element = pad.get_parent_element()
    clock = element.get_clock()
    base_time = element.get_base_time()
    frame_age = None
    if (
        clock is not None
        and base_time != Gst.CLOCK_TIME_NONE
        and buffer.pts != Gst.CLOCK_TIME_NONE
    ):
        frame_age = frame_age_seconds(
            clock.get_time(),
            base_time,
            buffer.pts,
        )

    if not frame_is_fresh(frame_age, config.MAX_FRAME_AGE):
        for detection in detections:
            if detection.get_label() in config.TARGET_LABELS:
                roi.remove_object(detection)

        with user_data.lock:
            user_data.bird_present = False
            user_data.new_frame = False
            user_data.stop_tracking = True
        user_data.aim_x, user_data.aim_y = 0.5, 0.5
        user_data.active_track_id = None
        user_data.recovery_mode = None
        user_data.target_predictor.reset()

        now = time.monotonic()
        if now - user_data.last_latency_warning_time >= 1.0:
            age = (
                "unknown"
                if frame_age is None
                else f"{frame_age * 1000:.0f} ms"
            )
            print(f"[LATENCY] Dropping stale control frame ({age})", flush=True)
            user_data.last_latency_warning_time = now

        if user_data.use_frame:
            cv2.putText(
                frame,
                "STALE FRAME",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
            )
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            user_data.set_frame(frame)
        return Gst.PadProbeReturn.OK

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

    targets = []
    for detection in detections:
        label = detection.get_label()
        confidence = detection.get_confidence()

        if not is_tracking_target(
            label,
            confidence,
            config.TARGET_LABELS,
            config.CONF_THRESH,
        ):
            if confidence <= config.CONF_THRESH:
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
        targets.append(
            (
                center_x,
                center_y,
                bbox,
                confidence,
                track_id,
                detection.get_class_id(),
                label,
            )
        )

    tracked = choose_target(
        targets,
        user_data.active_track_id,
        user_data.aim_x,
        user_data.aim_y,
    )
    recovery_target = None
    if tracked is not None:
        (
            center_x,
            center_y,
            bbox,
            confidence,
            track_id,
            class_id,
            label,
        ) = tracked
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
        with user_data.lock:
            was_present = user_data.bird_present
            user_data.target_error_x = predict_error(
                center_x - 0.5,
                user_data.target_predictor.velocity_x,
                config.CONTROL_LOOKAHEAD,
            )
            user_data.target_error_y = predict_error(
                center_y - 0.5,
                user_data.target_predictor.velocity_y,
                config.CONTROL_LOOKAHEAD,
            )
            user_data.bird_present = True
            user_data.last_bird_time = now
            user_data.new_frame = True
        if previous_recovery is not None:
            print(
                f"[TARGET] {label} reacquired "
                f"(id={track_id}, confidence={confidence:.2f})"
            )
        elif not was_present:
            print(
                f"[TARGET] {label} acquired "
                f"(id={track_id}, confidence={confidence:.2f})"
            )
    else:
        now = time.monotonic()
        prediction = user_data.target_predictor.predict(now)
        previous_recovery = user_data.recovery_mode
        with user_data.lock:
            was_present = user_data.bird_present
            last_seen = user_data.last_bird_time
            if prediction is not None:
                error_x, error_y, recovery_mode = prediction
                user_data.target_error_x = error_x
                user_data.target_error_y = error_y
                user_data.bird_present = True
                user_data.new_frame = True
            else:
                recovery_mode = None
                user_data.bird_present = False
                if was_present:
                    user_data.stop_tracking = True

        user_data.recovery_mode = recovery_mode
        if prediction is not None:
            recovery_target = error_x + 0.5, error_y + 0.5
            user_data.aim_x = max(0.0, min(1.0, recovery_target[0]))
            user_data.aim_y = max(0.0, min(1.0, recovery_target[1]))
            if recovery_mode != previous_recovery:
                print(f"[BIRD] Recovery: {recovery_mode}")

        if prediction is None and was_present:
            print("[TARGET] Target lost")

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
            f"Targets: {len(targets)}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
        )
        if user_data.recovery_mode is not None:
            cv2.putText(
                frame,
                f"Recovery: {user_data.recovery_mode}",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 165, 255),
                2,
            )

        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        user_data.set_frame(frame)

    return Gst.PadProbeReturn.OK
