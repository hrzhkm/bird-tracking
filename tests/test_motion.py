import math
import unittest
from collections import deque

from bird_tracker.motion import (
    SmoothedAxis,
    frame_age_seconds,
    frame_is_fresh,
    format_servo_command,
    format_velocity_command,
    predict_error,
    tracking_velocity,
)


class SmoothedAxisTests(unittest.TestCase):
    def test_filter_converges_without_jumping_to_new_sample(self):
        axis = SmoothedAxis(0.15, 0.06, 0.035)
        self.assertEqual(axis.update(0.0, 0.05), 0.0)

        filtered = axis.update(0.3, 0.05)

        self.assertGreater(filtered, 0.06)
        self.assertLess(filtered, 0.3)

    def test_deadzone_hysteresis_prevents_chatter(self):
        axis = SmoothedAxis(0.0, 0.06, 0.035)

        self.assertEqual(axis.update(0.05, 0.05), 0.0)
        self.assertEqual(axis.update(0.07, 0.05), 0.07)
        self.assertEqual(axis.update(0.04, 0.05), 0.04)
        self.assertEqual(axis.update(0.03, 0.05), 0.0)
        self.assertEqual(axis.update(0.05, 0.05), 0.0)

    def test_reset_seeds_filter_from_next_sample(self):
        axis = SmoothedAxis(0.15, 0.06, 0.035)
        axis.update(0.3, 0.05)
        axis.reset()

        self.assertEqual(axis.update(-0.2, 0.05), -0.2)


class MotionHelperTests(unittest.TestCase):
    def test_frame_age_uses_pipeline_running_time(self):
        self.assertEqual(
            frame_age_seconds(
                clock_time=2_000_000_000,
                base_time=1_000_000_000,
                presentation_time=750_000_000,
            ),
            0.25,
        )

    def test_stale_or_untimed_frames_are_rejected(self):
        self.assertTrue(frame_is_fresh(0.25, 0.25))
        self.assertFalse(frame_is_fresh(0.251, 0.25))
        self.assertFalse(frame_is_fresh(None, 0.25))

    def test_tracking_velocity_is_bounded_and_respects_direction(self):
        self.assertEqual(
            tracking_velocity(0.5, 1, 80.0, 30.0),
            30.0,
        )
        self.assertEqual(
            tracking_velocity(0.5, -1, 80.0, 30.0),
            -30.0,
        )

    def test_installed_tilt_direction_moves_targets_toward_center(self):
        top = tracking_velocity(
            error=-0.25,
            sign=-1,
            gain=60.0,
            maximum_speed=30.0,
        )
        bottom = tracking_velocity(
            error=0.25,
            sign=-1,
            gain=60.0,
            maximum_speed=30.0,
        )

        self.assertGreater(top, 0.0)
        self.assertLess(bottom, 0.0)

    def test_decimal_command_format(self):
        self.assertEqual(format_servo_command(70, 80.125), "70.00,80.12\n")

    def test_tracking_command_uses_velocities(self):
        self.assertEqual(
            format_velocity_command(12.625, -8.375),
            "V,12.62,-8.38\n",
        )

    def test_zero_error_commands_zero_velocity(self):
        self.assertEqual(
            tracking_velocity(
                error=0.0,
                sign=1,
                gain=80.0,
                maximum_speed=20.0,
            ),
            0.0,
        )

    def test_velocity_is_continuous_at_old_precision_boundary(self):
        below = tracking_velocity(
            error=0.249,
            sign=1,
            gain=80.0,
            maximum_speed=30.0,
        )
        above = tracking_velocity(
            error=0.251,
            sign=1,
            gain=80.0,
            maximum_speed=30.0,
        )

        self.assertLess(above - below, 0.2)

    def test_prediction_brakes_approach_and_is_bounded(self):
        self.assertAlmostEqual(predict_error(0.2, -0.5, 0.12), 0.14)
        self.assertEqual(predict_error(0.4, 2.0, 0.12), 0.5)

    def test_velocity_profile_settles_with_camera_delay_and_noise(self):
        acceleration = 180.0
        maximum_velocity = 30.0
        control_dt = 0.02
        frame_dt = 1 / 30
        camera_delay = 0.27
        field_of_view = 45.0
        bird_angle = 15.0
        position = 0.0
        velocity = 0.0
        commanded_velocity = 0.0
        next_frame = 0.0
        previous_error = None
        previous_sample = None
        estimated_screen_velocity = 0.0
        center_crossings = 0
        settled_errors = []
        position_history = deque([(0.0, position)])
        error_filter = SmoothedAxis(0.08, 0.01, 0.004)

        for tick in range(int(8 / control_dt)):
            now = tick * control_dt
            position_history.append((now, position))
            while (
                len(position_history) > 1
                and position_history[1][0] <= now - camera_delay
            ):
                position_history.popleft()

            if now + 1e-9 >= next_frame:
                delayed_position = position_history[0][1]
                sample = (
                    (bird_angle - delayed_position) / field_of_view
                    + 0.003 * math.sin(now * 17.0)
                )
                if previous_sample is not None:
                    measured_velocity = (
                        sample - previous_sample
                    ) / frame_dt
                    alpha = 1.0 - math.exp(-frame_dt / 0.15)
                    estimated_screen_velocity += alpha * (
                        measured_velocity - estimated_screen_velocity
                    )
                previous_sample = sample
                predicted = predict_error(
                    sample,
                    estimated_screen_velocity,
                    0.14,
                )
                filtered = error_filter.update(predicted, frame_dt)
                commanded_velocity = tracking_velocity(
                    filtered,
                    sign=1,
                    gain=80.0,
                    maximum_speed=maximum_velocity,
                )
                next_frame += frame_dt

                actual_error = (bird_angle - position) / field_of_view
                if (
                    previous_error is not None
                    and actual_error * previous_error < 0
                ):
                    center_crossings += 1
                previous_error = actual_error
                if now >= 6.0:
                    settled_errors.append(abs(actual_error))

            acceleration_step = acceleration * control_dt
            if velocity < commanded_velocity:
                velocity = min(
                    velocity + acceleration_step,
                    commanded_velocity,
                )
            else:
                velocity = max(
                    velocity - acceleration_step,
                    commanded_velocity,
                )
            position += velocity * control_dt

        self.assertEqual(center_crossings, 0)
        self.assertLess(settled_errors[-1], 0.01)


if __name__ == "__main__":
    unittest.main()
