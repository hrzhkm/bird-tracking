import pytest


pytest.importorskip("hailo_apps")

from bird_tracker import config, controller


def test_missing_cp2102_does_not_fall_back_to_another_serial_port(monkeypatch):
    monkeypatch.setattr(config, "SERIAL_PORT", None)
    monkeypatch.setattr(controller.glob, "glob", lambda _pattern: [])

    assert controller.find_servo_port() is None
