"""Short, bounded target prediction for recovering birds that leave frame."""

import math

from .motion import clamp


class LostTargetRecovery:
    """Estimate screen velocity and briefly coast through detector misses."""

    def __init__(
        self,
        velocity_tau,
        coast_seconds,
        minimum_speed,
        maximum_speed,
        prediction_margin,
    ):
        self.velocity_tau = velocity_tau
        self.coast_seconds = coast_seconds
        self.minimum_speed = minimum_speed
        self.maximum_speed = maximum_speed
        self.prediction_margin = prediction_margin
        self.reset()

    def reset(self):
        self.last_x = None
        self.last_y = None
        self.last_time = None
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.identity = None

    def observe(self, center_x, center_y, now, identity=None):
        identity_changed = (
            identity is not None
            and self.identity is not None
            and identity != self.identity
        )
        dt = None if self.last_time is None else now - self.last_time

        if identity_changed or dt is None or not 0.01 <= dt <= 0.5:
            self.velocity_x = 0.0
            self.velocity_y = 0.0
        else:
            measured_x = clamp(
                (center_x - self.last_x) / dt,
                -self.maximum_speed,
                self.maximum_speed,
            )
            measured_y = clamp(
                (center_y - self.last_y) / dt,
                -self.maximum_speed,
                self.maximum_speed,
            )
            alpha = (
                1.0
                if self.velocity_tau == 0
                else 1.0 - math.exp(-dt / self.velocity_tau)
            )
            self.velocity_x += alpha * (measured_x - self.velocity_x)
            self.velocity_y += alpha * (measured_y - self.velocity_y)

        self.last_x = center_x
        self.last_y = center_y
        self.last_time = now
        self.identity = identity

    def predict(self, now):
        """Return ``(error_x, error_y, mode)`` or ``None`` when recovery ends."""
        if self.last_time is None:
            return None

        age = max(now - self.last_time, 0.0)
        speed = math.hypot(self.velocity_x, self.velocity_y)
        if speed < self.minimum_speed:
            return None

        if age > self.coast_seconds:
            return None

        predicted_x = clamp(
            self.last_x + self.velocity_x * age,
            -self.prediction_margin,
            1.0 + self.prediction_margin,
        )
        predicted_y = clamp(
            self.last_y + self.velocity_y * age,
            -self.prediction_margin,
            1.0 + self.prediction_margin,
        )
        return predicted_x - 0.5, predicted_y - 0.5, "coast"
