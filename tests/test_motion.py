import math
import unittest
from collections import deque

from bird_tracker.motion import (
    SmoothedAxis,
    format_servo_command,
    format_tracking_command,
    move_toward_at_speed,
    servo_command_is_stale,
    track_axis,
    tracking_delta,
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
    def test_tracking_speed_is_limited_and_frame_rate_independent(self):
        one_step = track_axis(0.0, 0.5, 0.1, 1, 140.0, 30.0, -80, 80)
        two_steps = track_axis(0.0, 0.5, 0.05, 1, 140.0, 30.0, -80, 80)
        two_steps = track_axis(
            two_steps, 0.5, 0.05, 1, 140.0, 30.0, -80, 80
        )

        self.assertAlmostEqual(one_step, 3.0)
        self.assertAlmostEqual(two_steps, one_step)

    def test_tracking_respects_direction_and_joint_limit(self):
        self.assertEqual(
            track_axis(79.0, 0.5, 0.1, 1, 140.0, 30.0, -80, 80),
            80,
        )
        self.assertAlmostEqual(
            track_axis(0.0, 0.5, 0.1, -1, 140.0, 30.0, -80, 80),
            -3.0,
        )

    def test_positive_vertical_error_commands_downward_tilt(self):
        # Image Y increases downward, and increasing the installed tilt
        # servo angle points the camera downward.
        tilt = track_axis(
            current=0.0,
            error=0.25,
            dt=0.1,
            sign=1,
            gain=140.0,
            maximum_speed=30.0,
            low=-70.0,
            high=30.0,
        )

        self.assertGreater(tilt, 0.0)

    def test_homing_uses_elapsed_time_and_does_not_overshoot(self):
        self.assertAlmostEqual(move_toward_at_speed(10, 0, 20, 0.1), 8)
        self.assertEqual(move_toward_at_speed(1, 0, 20, 0.1), 0)

    def test_decimal_command_format(self):
        self.assertEqual(format_servo_command(70, 80.125), "70.00,80.12\n")

    def test_tracking_command_uses_relative_deltas(self):
        self.assertEqual(
            format_tracking_command(0.625, -0.375),
            "R,0.62,-0.38\n",
        )

    def test_zero_error_cancels_queued_tracking_movement(self):
        self.assertEqual(
            tracking_delta(
                error=0.0,
                dt=0.1,
                sign=1,
                gain=90.0,
                maximum_speed=20.0,
            ),
            0.0,
        )

    def test_servo_resyncs_after_firmware_detach_window(self):
        self.assertFalse(
            servo_command_is_stale(
                now=12.4,
                last_command_time=10.0,
                idle_threshold=2.5,
            )
        )
        self.assertTrue(
            servo_command_is_stale(
                now=12.5,
                last_command_time=10.0,
                idle_threshold=2.5,
            )
        )

    def test_servo_without_command_history_requires_sync(self):
        self.assertTrue(
            servo_command_is_stale(
                now=10.0,
                last_command_time=None,
                idle_threshold=2.5,
            )
        )

    def test_fast_profile_is_limited_to_two_degrees_per_frame(self):
        delta = tracking_delta(
            error=0.5,
            dt=1 / 15,
            sign=1,
            gain=130.0,
            maximum_speed=30.0,
        )

        self.assertAlmostEqual(delta, 2.0)

    def test_precision_gain_brakes_near_center(self):
        delta = tracking_delta(
            error=0.1,
            dt=0.1,
            sign=1,
            gain=130.0,
            maximum_speed=30.0,
            precision_gain=20.0,
            precision_zone=0.25,
        )

        self.assertAlmostEqual(delta, 0.2)

    def test_fast_profile_settles_with_camera_delay(self):
        acceleration = 180.0
        maximum_velocity = 60.0
        control_dt = 0.02
        frame_dt = 1 / 15
        camera_delay = 0.27
        field_of_view = 60.0
        bird_angle = 18.0
        position = 0.0
        target = 0.0
        velocity = 0.0
        next_frame = 0.0
        previous_error = None
        center_crossings = 0
        settled_errors = []
        position_history = deque([(0.0, position)])
        error_filter = SmoothedAxis(0.02, 0.01, 0.004)

        for tick in range(int(12 / control_dt)):
            now = tick * control_dt
            position_history.append((now, position))
            while (
                len(position_history) > 1
                and position_history[1][0] <= now - camera_delay
            ):
                position_history.popleft()

            if now + 1e-9 >= next_frame:
                delayed_position = position_history[0][1]
                error = (bird_angle - delayed_position) / field_of_view
                filtered = error_filter.update(error, frame_dt)
                delta = tracking_delta(
                    filtered,
                    frame_dt,
                    sign=1,
                    gain=130.0,
                    maximum_speed=30.0,
                    precision_gain=20.0,
                    precision_zone=0.25,
                )
                if delta == 0.0 or delta * velocity < 0.0:
                    velocity = 0.0
                target = position + max(-3.0, min(3.0, delta))
                next_frame += frame_dt

                actual_error = (bird_angle - position) / field_of_view
                if (
                    previous_error is not None
                    and actual_error * previous_error < 0
                ):
                    center_crossings += 1
                previous_error = actual_error
                if now >= 10.0:
                    settled_errors.append(abs(actual_error))

            distance = target - position
            acceleration_step = acceleration * control_dt
            if (
                abs(distance) <= 0.01
                and abs(velocity) <= acceleration_step
            ):
                position = target
                velocity = 0.0
                continue

            stopping_speed = (
                math.sqrt(
                    acceleration_step**2
                    + 2.0 * acceleration * abs(distance)
                )
                - acceleration_step
            )
            desired_velocity = math.copysign(
                min(maximum_velocity, stopping_speed),
                distance,
            )
            if velocity < desired_velocity:
                velocity = min(
                    velocity + acceleration_step,
                    desired_velocity,
                )
            else:
                velocity = max(
                    velocity - acceleration_step,
                    desired_velocity,
                )

            next_position = position + velocity * control_dt
            crossed_target = (
                distance >= 0.0
                and velocity > 0.0
                and next_position >= target
            ) or (
                distance <= 0.0
                and velocity < 0.0
                and next_position <= target
            )
            if crossed_target:
                position = target
                velocity = 0.0
            else:
                position = next_position

        self.assertEqual(center_crossings, 0)
        self.assertLess(settled_errors[-1], 0.004)


if __name__ == "__main__":
    unittest.main()
