"""Bird tracker application entry point."""

import gi

gi.require_version("Gst", "1.0")

from hailo_apps.hailo_app_python.core.common.core import get_default_parser

from . import config
from .controller import BirdTrackerState
from .detection import app_callback
from .focus import create_focus_window
from .pipeline import LowLatencyDetectionApp


def main():
    parser = get_default_parser()
    parser.set_defaults(
        input=config.VIDEO_SOURCE,
        frame_rate=config.FRAME_RATE,
        hef_path=config.HEF_PATH,
        labels_json=config.LABELS_JSON,
    )

    user_data = BirdTrackerState()
    app = LowLatencyDetectionApp(app_callback, user_data, parser=parser)
    focus_window = create_focus_window(app.video_source)
    try:
        app.run()
    finally:
        if focus_window is not None:
            focus_window.destroy()
        user_data.shutdown()
