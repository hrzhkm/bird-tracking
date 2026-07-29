"""Dependency-free motion helpers for smooth bird tracking."""

import math


def clamp(value, low, high):
    return low if value < low else high if value > high else value


def predict_error(error, screen_velocity, lookahead):
    """Project a delayed image error to the expected control time."""
    return clamp(error + screen_velocity * lookahead, -0.5, 0.5)


def tracking_velocity(error, sign, gain, maximum_speed):
    """Convert image error into a bounded servo velocity."""
    return sign * clamp(gain * error, -maximum_speed, maximum_speed)


def format_servo_command(pan_degrees, tilt_degrees):
    """Serialize sub-degree targets while remaining human-readable."""
    return f"{pan_degrees:.2f},{tilt_degrees:.2f}\n"


def format_velocity_command(pan_velocity, tilt_velocity):
    """Serialize desired tracking velocities in degrees per second."""
    return f"V,{pan_velocity:.2f},{tilt_velocity:.2f}\n"


class SmoothedAxis:
    """Time-aware low-pass filter with dead-zone hysteresis."""

    def __init__(self, time_constant, enter_deadzone, exit_deadzone):
        self.time_constant = time_constant
        self.enter_deadzone = enter_deadzone
        self.exit_deadzone = exit_deadzone
        self.value = None
        self.active = False

    def reset(self):
        self.value = None
        self.active = False

    def update(self, sample, dt):
        if self.value is None:
            self.value = sample
        elif self.time_constant == 0:
            self.value = sample
        else:
            alpha = 1.0 - math.exp(-max(dt, 0.0) / self.time_constant)
            self.value += alpha * (sample - self.value)

        magnitude = abs(self.value)
        if self.active:
            if magnitude <= self.exit_deadzone:
                self.active = False
        elif magnitude >= self.enter_deadzone:
            self.active = True

        return self.value if self.active else 0.0
