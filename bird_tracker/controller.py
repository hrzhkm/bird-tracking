"""Servo discovery, serial I/O, and the bird tracking control loop."""

import glob
import threading
import time

import serial
from hailo_apps.hailo_app_python.core.gstreamer.gstreamer_app import (
    app_callback_class,
)

from . import config
from .motion import (
    SmoothedAxis,
    clamp,
    format_servo_command,
    format_tracking_command,
    servo_command_is_stale,
    tracking_delta,
)
from .prediction import LostTargetRecovery


def find_servo_port():
    """Find the configured servo controller, preferring its stable USB ID."""
    if config.SERIAL_PORT:
        return config.SERIAL_PORT

    preferred = sorted(glob.glob("/dev/serial/by-id/*USB_Single_Serial*"))
    if preferred:
        return preferred[0]

    fallback = sorted(glob.glob("/dev/ttyACM*"))
    return fallback[0] if fallback else None


class BirdTrackerState(app_callback_class):
    """Shared detection state and the servo control worker."""

    def __init__(self):
        super().__init__()

        # Establish the intended position before opening serial. The controller
        # may reset as the port opens, so startup repeatedly sends these values
        # until its boot window has elapsed.
        self.pan_angle = config.HOME_PAN
        self.tilt_angle = config.HOME_TILT
        self._last_command_time = None
        self._resync_until = None

        self.serial_port = find_servo_port() if config.SERVO_ENABLED else None
        if not config.SERVO_ENABLED:
            self.ser = None
            print("[SERVO] Disabled for safe model testing")
        else:
            try:
                if self.serial_port is None:
                    raise serial.SerialException(
                        "no servo controller found under "
                        "/dev/serial/by-id or /dev/ttyACM*"
                    )
                self.ser = serial.Serial()
                self.ser.port = self.serial_port
                self.ser.baudrate = config.SERIAL_BAUD
                self.ser.timeout = 0
                self.ser.dtr = False
                self.ser.rts = False
                self.ser.open()
                print(
                    f"[SERVO] Connected to {self.serial_port} "
                    f"at {config.SERIAL_BAUD} baud"
                )
                self._home_on_startup()
            except serial.SerialException as error:
                print(f"[WARN] Servo control disabled: {error}")
                self.ser = None

        self.lock = threading.Lock()
        self.bird_present = False
        self.target_error_x = 0.0
        self.target_error_y = 0.0
        # Give the servos time to physically reach home before the idle
        # controller detaches them.
        self.last_bird_time = time.monotonic()
        self.new_frame = False
        self.stop_tracking = False

        # Callback-only sticky aim point used to select the nearest target.
        self.aim_x = 0.5
        self.aim_y = 0.5
        self.last_bird_bbox = None
        self.last_bird_confidence = 0.0
        self.last_target_class_id = None
        self.last_target_label = None
        self.last_detection_debug_time = 0.0
        self.active_track_id = None
        self.recovery_mode = None
        self.target_predictor = LostTargetRecovery(
            config.PREDICTION_VELOCITY_TAU,
            config.PREDICTION_COAST,
            config.PREDICTION_SEARCH,
            config.PREDICTION_MIN_SPEED,
            config.PREDICTION_MAX_SPEED,
            config.PREDICTION_EDGE_ZONE,
            config.PREDICTION_SEARCH_ERROR,
            config.PREDICTION_MARGIN,
        )
        self._pan_filter = SmoothedAxis(
            config.TARGET_FILTER_TAU,
            config.DEADZONE_ENTER,
            config.DEADZONE_EXIT,
        )
        self._tilt_filter = SmoothedAxis(
            config.TARGET_FILTER_TAU,
            config.DEADZONE_ENTER,
            config.DEADZONE_EXIT,
        )
        self._last_tracking_update = None
        self._home_commanded = False

        self._running = True
        self._thread = threading.Thread(target=self._control_loop, daemon=True)
        self._thread.start()

    def _home_on_startup(self):
        """Keep asserting home while the serial controller finishes booting."""
        deadline = time.monotonic() + config.STARTUP_HOME_DURATION
        while True:
            self._send(self.pan_angle, self.tilt_angle)
            if time.monotonic() >= deadline:
                break
            time.sleep(config.STARTUP_HOME_INTERVAL)

        print(
            f"[SERVO] Homed to pan={self.pan_angle + 90:g}, "
            f"tilt={self.tilt_angle + 90:g}"
        )

    def _send(self, pan_degrees, tilt_degrees):
        if self.ser is None:
            return

        pan_wire = clamp(pan_degrees, config.PAN_MIN, config.PAN_MAX) + 90
        tilt_wire = clamp(tilt_degrees, config.TILT_MIN, config.TILT_MAX) + 90
        try:
            waiting = self.ser.in_waiting
            if waiting:
                self.ser.read(waiting)
            self.ser.write(format_servo_command(pan_wire, tilt_wire).encode())
            self._last_command_time = time.monotonic()
        except serial.SerialException as error:
            print(f"[WARN] Serial write failed: {error}")

    def _detach(self):
        if self.ser is None:
            return
        try:
            self.ser.write(b"D\n")
            self._last_command_time = None
        except serial.SerialException:
            pass

    def _send_tracking(self, pan_delta, tilt_delta):
        if self.ser is None:
            return

        try:
            waiting = self.ser.in_waiting
            if waiting:
                self.ser.read(waiting)
            command = format_tracking_command(pan_delta, tilt_delta)
            self.ser.write(command.encode())
            self._last_command_time = time.monotonic()
        except serial.SerialException as error:
            print(f"[WARN] Serial write failed: {error}")

    def _control_loop(self):
        """Send all servo commands from one control thread."""
        while self._running:
            now = time.monotonic()

            with self.lock:
                bird = self.bird_present
                error_x = self.target_error_x
                error_y = self.target_error_y
                last_seen = self.last_bird_time
                fresh = self.new_frame
                stop = self.stop_tracking
                self.new_frame = False
                self.stop_tracking = False

            if stop:
                self._send_tracking(0.0, 0.0)
                self._reset_tracking()

            if bird and fresh:
                if not self._wait_for_servo_sync(now):
                    if self._last_tracking_update is None:
                        tracking_dt = min(
                            1.0 / config.FRAME_RATE,
                            config.MAX_CONTROL_DT,
                        )
                    else:
                        tracking_dt = min(
                            max(now - self._last_tracking_update, 0.0),
                            config.MAX_CONTROL_DT,
                        )
                    self._last_tracking_update = now
                    pan_delta, tilt_delta = self._track_step(
                        error_x,
                        error_y,
                        tracking_dt,
                    )
                    self._send_tracking(pan_delta, tilt_delta)
                    self._home_commanded = False
            elif not bird:
                self._reset_tracking()
                if (
                    now - last_seen > config.HOME_TIMEOUT
                    and not self._home_commanded
                ):
                    self.pan_angle = config.HOME_PAN
                    self.tilt_angle = config.HOME_TILT
                    self._send(self.pan_angle, self.tilt_angle)
                    self._home_commanded = True

            time.sleep(config.CONTROL_DT)

    def _wait_for_servo_sync(self, now):
        if self._resync_until is not None:
            if now < self._resync_until:
                return True
            self._resync_until = None
            self._reset_tracking()
            print("[SERVO] Position synchronized; tracking")
            return False

        if not servo_command_is_stale(
            now,
            self._last_command_time,
            config.SERVO_RESYNC_IDLE,
        ):
            return False

        self._send(self.pan_angle, self.tilt_angle)
        self._resync_until = now + config.SERVO_RESYNC_SETTLE
        self._reset_tracking()
        print("[SERVO] Re-synchronizing position before tracking")
        return config.SERVO_RESYNC_SETTLE > 0

    def _track_step(self, error_x, error_y, dt):
        filtered_x = self._pan_filter.update(error_x, dt)
        filtered_y = self._tilt_filter.update(error_y, dt)
        pan_delta = tracking_delta(
            filtered_x,
            dt,
            config.PAN_SIGN,
            config.TRACK_GAIN,
            config.MAX_TARGET_SPEED,
            config.PRECISION_GAIN,
            config.PRECISION_ZONE,
        )
        tilt_delta = tracking_delta(
            filtered_y,
            dt,
            config.TILT_SIGN,
            config.TRACK_GAIN,
            config.MAX_TARGET_SPEED,
            config.PRECISION_GAIN,
            config.PRECISION_ZONE,
        )
        self.pan_angle = clamp(
            self.pan_angle + pan_delta,
            config.PAN_MIN,
            config.PAN_MAX,
        )
        self.tilt_angle = clamp(
            self.tilt_angle + tilt_delta,
            config.TILT_MIN,
            config.TILT_MAX,
        )
        return pan_delta, tilt_delta

    def _reset_tracking(self):
        if self._last_tracking_update is None:
            return
        self._pan_filter.reset()
        self._tilt_filter.reset()
        self._last_tracking_update = None

    def shutdown(self):
        """Stop the worker, release the servos, and close the serial port."""
        self._running = False
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._detach()
        if self.ser is not None:
            self.ser.close()
