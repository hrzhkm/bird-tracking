"""Bird tracker application entry point."""

import gi

gi.require_version("Gst", "1.0")

from hailo_apps.hailo_app_python.core.common.core import get_default_parser

from . import config
from .controller import BirdTrackerState
from .detection import app_callback
from .pipeline import LowLatencyDetectionApp


def main():
    parser = get_default_parser()
    parser.set_defaults(input=config.VIDEO_SOURCE)

    user_data = BirdTrackerState()
    app = LowLatencyDetectionApp(app_callback, user_data, parser=parser)
    try:
        app.run()
    finally:
        user_data.shutdown()
