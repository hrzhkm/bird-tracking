"""Servo discovery, serial I/O, and the bird tracking control loop."""

import glob
import threading
import time

import serial
from hailo_apps.hailo_app_python.core.gstreamer.gstreamer_app import (
    app_callback_class,
)

from . import config


def clamp(value, low, high):
    return low if value < low else high if value > high else value


def move_toward(current, target, step):
    if current < target:
        return min(current + step, target)
    return max(current - step, target)


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

        self.serial_port = find_servo_port()
        try:
            if self.serial_port is None:
                raise serial.SerialException(
                    "no servo controller found under /dev/serial/by-id or /dev/ttyACM*"
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
            time.sleep(2.0)
        except serial.SerialException as error:
            print(f"[WARN] Servo control disabled: {error}")
            self.ser = None

        self.pan_angle = config.HOME_PAN
        self.tilt_angle = config.HOME_TILT

        self.lock = threading.Lock()
        self.bird_present = False
        self.target_error_x = 0.0
        self.target_error_y = 0.0
        # Give the servos time to physically reach home before the idle
        # controller detaches them.
        self.last_bird_time = time.time()
        self.new_frame = False

        # Callback-only sticky aim point used to select the nearest target.
        self.aim_x = 0.5
        self.aim_y = 0.5
        self.last_bird_bbox = None
        self.last_bird_confidence = 0.0

        self._detached = False
        self._running = True
        self._send(self.pan_angle, self.tilt_angle)
        self._thread = threading.Thread(target=self._control_loop, daemon=True)
        self._thread.start()

    def _send(self, pan_degrees, tilt_degrees):
        if self.ser is None:
            return

        pan_wire = int(
            round(clamp(pan_degrees, config.PAN_MIN, config.PAN_MAX) + 90)
        )
        tilt_wire = int(
            round(clamp(tilt_degrees, config.TILT_MIN, config.TILT_MAX) + 90)
        )
        try:
            waiting = self.ser.in_waiting
            if waiting:
                self.ser.read(waiting)
            self.ser.write(f"{pan_wire},{tilt_wire}\n".encode())
        except serial.SerialException as error:
            print(f"[WARN] Serial write failed: {error}")

    def _detach(self):
        if self.ser is None:
            return
        try:
            self.ser.write(b"D\n")
        except serial.SerialException:
            pass

    def _control_loop(self):
        """Send all servo commands from one control thread."""
        while self._running:
            with self.lock:
                bird = self.bird_present
                error_x = self.target_error_x
                error_y = self.target_error_y
                last_seen = self.last_bird_time
                fresh = self.new_frame
                self.new_frame = False

            if bird and fresh:
                self._track_step(error_x, error_y)
                self._send(self.pan_angle, self.tilt_angle)
                self._detached = False
            elif not bird and time.time() - last_seen > config.HOME_TIMEOUT:
                moved = self._home_step()
                if moved:
                    self._send(self.pan_angle, self.tilt_angle)
                elif not self._detached:
                    self._detach()
                    self._detached = True

            time.sleep(config.CONTROL_DT)

    def _track_step(self, error_x, error_y):
        if abs(error_x) > config.DEADZONE:
            step = clamp(config.KP * error_x, -config.MAX_STEP, config.MAX_STEP)
            self.pan_angle = clamp(
                self.pan_angle + config.PAN_SIGN * step,
                config.PAN_MIN,
                config.PAN_MAX,
            )
        if abs(error_y) > config.DEADZONE:
            step = clamp(config.KP * error_y, -config.MAX_STEP, config.MAX_STEP)
            self.tilt_angle = clamp(
                self.tilt_angle + config.TILT_SIGN * step,
                config.TILT_MIN,
                config.TILT_MAX,
            )

    def _home_step(self):
        moved = False
        if abs(self.pan_angle - config.HOME_PAN) > 0.01:
            self.pan_angle = move_toward(
                self.pan_angle, config.HOME_PAN, config.MAX_STEP
            )
            moved = True
        if abs(self.tilt_angle - config.HOME_TILT) > 0.01:
            self.tilt_angle = move_toward(
                self.tilt_angle, config.HOME_TILT, config.MAX_STEP
            )
            moved = True
        return moved

    def shutdown(self):
        """Stop the worker, release the servos, and close the serial port."""
        self._running = False
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._detach()
        if self.ser is not None:
            self.ser.close()
