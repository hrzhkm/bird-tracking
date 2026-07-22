"""Stable, low-latency Hailo bird detection pipeline."""

from hailo_apps.hailo_app_python.apps.detection.detection_pipeline import (
    GStreamerDetectionApp,
)
from hailo_apps.hailo_app_python.core.gstreamer.gstreamer_helper_pipelines import (
    DISPLAY_PIPELINE,
    INFERENCE_PIPELINE,
    INFERENCE_PIPELINE_WRAPPER,
    SOURCE_PIPELINE,
    USER_CALLBACK_PIPELINE,
)

from . import config


class LowLatencyDetectionApp(GStreamerDetectionApp):
    """Detection pipeline without Hailo's redundant native object tracker."""

    def get_pipeline_string(self):
        source_pipeline = SOURCE_PIPELINE(
            video_source=self.video_source,
            video_width=640,
            video_height=480,
            frame_rate=self.frame_rate,
            sync=self.sync,
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
            bypass_max_size_buffers=3,
        )
        callback_pipeline = USER_CALLBACK_PIPELINE()
        display_pipeline = DISPLAY_PIPELINE(
            video_sink=config.VIDEO_SINK,
            sync=self.sync,
            show_fps=self.show_fps,
        )

        pipeline = (
            f"{source_pipeline} ! "
            f"{inference_wrapper} ! "
            f"{callback_pipeline} ! "
            f"{display_pipeline}"
        )
        pipeline = pipeline.replace("leaky=no", "leaky=downstream")
        print(
            "[BIRD TRACKER] "
            f"confidence={config.CONF_THRESH:.2f}, "
            f"fps={self.frame_rate}, batch=1, "
            f"native-tracker=off, sink={config.VIDEO_SINK}"
        )
        return pipeline
