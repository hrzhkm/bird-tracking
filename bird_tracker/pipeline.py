"""Hailo detection pipeline customizations."""

import io
from contextlib import redirect_stdout

from hailo_apps.hailo_app_python.apps.detection.detection_pipeline import (
    GStreamerDetectionApp,
)

from . import config


class LowLatencyDetectionApp(GStreamerDetectionApp):
    """Detection pipeline configured for lower-latency tracking."""

    def get_pipeline_string(self):
        # The base implementation prints its generic template before we apply
        # bird-specific values, which is misleading in normal tracker output.
        with redirect_stdout(io.StringIO()):
            pipeline = super().get_pipeline_string()
        pipeline = pipeline.replace("leaky=no", "leaky=downstream")
        pipeline = pipeline.replace("width=1280", "width=640")
        pipeline = pipeline.replace("height=720", "height=480")
        pipeline = pipeline.replace(
            "nms-score-threshold=0.3",
            f"nms-score-threshold={config.CONF_THRESH}",
        )
        pipeline = pipeline.replace(
            "class-id=1",
            f"class-id={config.BIRD_CLASS_ID}",
        )
        print(
            "[BIRD TRACKER] "
            f"class-id={config.BIRD_CLASS_ID}, "
            f"confidence={config.CONF_THRESH:.2f}"
        )
        return pipeline
