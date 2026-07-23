"""Dependency-free motion helpers for smooth bird tracking."""

import math


def clamp(value, low, high):
    return low if value < low else high if value > high else value


def move_toward(current, target, maximum_delta):
    if current < target:
        return min(current + maximum_delta, target)
    return max(current - maximum_delta, target)


def move_toward_at_speed(current, target, speed, dt):
    """Move toward a position at a rate expressed in degrees per second."""
    return move_toward(current, target, speed * max(dt, 0.0))


def tracking_delta(error, dt, sign, gain, maximum_speed):
    """Convert image error into a bounded relative servo movement."""
    velocity = clamp(gain * error, -maximum_speed, maximum_speed)
    return sign * velocity * max(dt, 0.0)


def track_axis(current, error, dt, sign, gain, maximum_speed, low, high):
    """Integrate a normalized image error into a bounded angular target."""
    delta = tracking_delta(error, dt, sign, gain, maximum_speed)
    return clamp(current + delta, low, high)


def format_servo_command(pan_degrees, tilt_degrees):
    """Serialize sub-degree targets while remaining human-readable."""
    return f"{pan_degrees:.2f},{tilt_degrees:.2f}\n"


def format_tracking_command(pan_delta, tilt_delta):
    """Serialize a relative tracking movement."""
    return f"R,{pan_delta:.2f},{tilt_delta:.2f}\n"


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
