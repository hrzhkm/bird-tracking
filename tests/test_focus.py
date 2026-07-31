from bird_tracker.focus import FOCUS_DEFAULT, focus_command, load_focus


def test_focus_value_and_commands(tmp_path):
    saved = tmp_path / "focus"
    assert load_focus(saved) == FOCUS_DEFAULT

    saved.write_text("2000\n")
    assert load_focus(saved) == 1023
    assert focus_command("/dev/video0", 450) == [
        "v4l2-ctl",
        "-d",
        "/dev/video0",
        "--set-ctrl=focus_automatic_continuous=0,focus_absolute=450",
    ]
    assert focus_command("/dev/video0")[-1] == (
        "--set-ctrl=focus_automatic_continuous=1"
    )
