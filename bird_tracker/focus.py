"""Small manual-focus control for V4L2 USB cameras."""

import os
import subprocess
from pathlib import Path


FOCUS_MIN = 1
FOCUS_MAX = 1023
FOCUS_DEFAULT = 512
FOCUS_FILE = (
    Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    / "bird-tracker"
    / "focus"
)


def clamp_focus(value):
    return max(FOCUS_MIN, min(FOCUS_MAX, int(value)))


def load_focus(path=FOCUS_FILE):
    try:
        return clamp_focus(path.read_text().strip())
    except (OSError, ValueError):
        return FOCUS_DEFAULT


def focus_commands(device, value=None):
    if value is None:
        return [[
            "v4l2-ctl",
            "-d",
            device,
            "--set-ctrl=focus_automatic_continuous=1",
        ]]
    return [
        [
            "v4l2-ctl",
            "-d",
            device,
            "--set-ctrl=focus_automatic_continuous=0",
        ],
        [
            "v4l2-ctl",
            "-d",
            device,
            f"--set-ctrl=focus_absolute={clamp_focus(value)}",
        ],
    ]


def create_focus_window(device):
    """Create a floating GTK focus panel for a resolved V4L2 device."""
    if not device.startswith("/dev/video"):
        return None

    os.environ.setdefault("GDK_BACKEND", "x11")
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk

    focus = load_focus()
    pending_update = None

    window = Gtk.Window(title="Camera Focus")
    window.set_keep_above(True)
    window.set_resizable(False)
    window.move(20, 80)

    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    row.set_border_width(10)
    window.add(row)

    scale = Gtk.Scale.new_with_range(
        Gtk.Orientation.HORIZONTAL,
        FOCUS_MIN,
        FOCUS_MAX,
        1,
    )
    scale.set_digits(0)
    scale.set_size_request(320, -1)
    scale.set_value(focus)

    automatic = Gtk.ToggleButton(label="Auto Focus")
    status = Gtk.Label(label="")

    row.pack_start(Gtk.Label(label="Focus"), False, False, 0)
    row.pack_start(scale, True, True, 0)
    row.pack_start(automatic, False, False, 0)
    row.pack_start(status, False, False, 0)

    def apply(commands):
        for command in commands:
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                status.set_text("Camera unavailable")
                print(f"[FOCUS] {error}", flush=True)
                return False
            if result.returncode != 0:
                status.set_text("Camera unavailable")
                print(
                    f"[FOCUS] "
                    f"{result.stderr.strip() or 'camera control failed'}",
                    flush=True,
                )
                return False
        status.set_text("")
        return True

    def apply_manual():
        nonlocal pending_update
        pending_update = None
        value = clamp_focus(scale.get_value())
        if apply(focus_commands(device, value)):
            try:
                FOCUS_FILE.parent.mkdir(parents=True, exist_ok=True)
                FOCUS_FILE.write_text(f"{value}\n")
            except OSError as error:
                print(f"[FOCUS] Could not save focus: {error}", flush=True)
        return False

    def schedule_manual(_scale):
        nonlocal pending_update
        if automatic.get_active():
            return
        if pending_update is not None:
            GLib.source_remove(pending_update)
        pending_update = GLib.timeout_add(150, apply_manual)

    def toggle_auto(button):
        nonlocal pending_update
        if pending_update is not None:
            GLib.source_remove(pending_update)
            pending_update = None
        enabled = button.get_active()
        scale.set_sensitive(not enabled)
        if enabled:
            apply(focus_commands(device))
        else:
            apply_manual()

    scale.connect("value-changed", schedule_manual)
    automatic.connect("toggled", toggle_auto)
    apply_manual()
    window.show_all()
    return window
