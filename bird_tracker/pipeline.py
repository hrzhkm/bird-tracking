"""Stable, low-latency Hailo bird detection pipeline."""

from hailo_apps.hailo_app_python.apps.detection.detection_pipeline import (
    GStreamerDetectionApp,
)
from hailo_apps.hailo_app_python.core.gstreamer.gstreamer_helper_pipelines import (
    DISPLAY_PIPELINE,
    INFERENCE_PIPELINE,
    INFERENCE_PIPELINE_WRAPPER,
    SOURCE_PIPELINE,
    TRACKER_PIPELINE,
    USER_CALLBACK_PIPELINE,
)

from . import config


def _limit_queue(pipeline, name, leaky="no"):
    old = f"name={name} leaky=no max-size-buffers=3"
    if old not in pipeline:
        raise RuntimeError(f"Hailo pipeline queue not found: {name}")
    return pipeline.replace(
        old,
        f"name={name} leaky={leaky} max-size-buffers=1",
        1,
    )


class LowLatencyDetectionApp(GStreamerDetectionApp):
    """Low-latency Hailo detection with metadata object tracking."""

    def get_pipeline_string(self):
        source_pipeline = SOURCE_PIPELINE(
            video_source=self.video_source,
            video_width=640,
            video_height=480,
            frame_rate=self.frame_rate,
            sync=self.sync,
        )
        if self.video_source.startswith("/dev/video"):
            source_pipeline = source_pipeline.replace(
                "v4l2src ",
                'v4l2src extra-controls="c,focus_automatic_continuous=0" ',
                1,
            )

        thresholds = (
            f"nms-score-threshold={config.CONF_THRESH} "
            "nms-iou-threshold=0.45 "
            "output-format-type=HAILO_FORMAT_TYPE_FLOAT32"
        )
        inference_pipeline = INFERENCE_PIPELINE(
            hef_path=self.hef_path,
            post_process_so=self.post_process_so,
            post_function_name=self.post_function_name,
            batch_size=1,
            config_json=self.labels_json,
            additional_params=thresholds,
        )
        inference_wrapper = INFERENCE_PIPELINE_WRAPPER(
            inference_pipeline,
            bypass_max_size_buffers=1,
        )
        inference_wrapper = _limit_queue(
            inference_wrapper,
            "inference_wrapper_input_q",
            "downstream",
        )
        inference_wrapper = _limit_queue(
            inference_wrapper,
            "inference_wrapper_output_q",
            "downstream",
        )
        tracker_pipeline = TRACKER_PIPELINE(
            class_id=-1,
            keep_new_frames=config.TRACKER_KEEP_NEW_FRAMES,
            keep_tracked_frames=config.TRACKER_KEEP_TRACKED_FRAMES,
            keep_lost_frames=config.TRACKER_KEEP_LOST_FRAMES,
            keep_past_metadata=True,
            qos=False,
        )
        tracker_pipeline = _limit_queue(tracker_pipeline, "hailo_tracker_q")
        callback_pipeline = USER_CALLBACK_PIPELINE()
        callback_pipeline = _limit_queue(callback_pipeline, "identity_callback_q")
        version_overlay = (
            f'textoverlay text="Model: {config.MODEL_VERSION}" '
            'valignment=bottom halignment=left '
            'font-desc="Sans 14" shaded-background=true'
        )
        display_pipeline = DISPLAY_PIPELINE(
            video_sink=config.VIDEO_SINK,
            sync=self.sync,
            show_fps=self.show_fps,
        )
        display_pipeline = _limit_queue(
            display_pipeline,
            "hailo_display_overlay_q",
            "downstream",
        )
        display_pipeline = _limit_queue(
            display_pipeline,
            "hailo_display_videoconvert_q",
        )
        display_pipeline = _limit_queue(display_pipeline, "hailo_display_q")

        pipeline = (
            f"{source_pipeline} ! "
            f"{inference_wrapper} ! "
            f"{tracker_pipeline} ! "
            f"{callback_pipeline} ! "
            f"{version_overlay} ! "
            f"{display_pipeline}"
        )
        print(
            "[BIRD TRACKER] "
            f"confidence={config.CONF_THRESH:.2f}, "
            f"fps={self.frame_rate}, batch=1, "
            f"hailo-tracker=on/"
            f"{config.TRACKER_KEEP_TRACKED_FRAMES}+"
            f"{config.TRACKER_KEEP_LOST_FRAMES}-frames, "
            f"model={config.MODEL_VERSION}, "
            f"sink={config.VIDEO_SINK}"
        )
        return pipeline
