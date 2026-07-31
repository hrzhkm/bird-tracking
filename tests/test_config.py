import os
import subprocess
import sys


def test_invalid_tracking_speed_and_boost_are_rejected():
    for variable, value in (
        ("TRACKING_MAX_SPEED", "61"),
        ("TRACKING_FAR_BOOST", "-1"),
    ):
        environment = os.environ.copy()
        environment[variable] = value
        result = subprocess.run(
            [sys.executable, "-c", "import bird_tracker.config"],
            env=environment,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert variable in result.stderr
