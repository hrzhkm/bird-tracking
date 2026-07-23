import unittest

from bird_tracker.motion import (
    SmoothedAxis,
    format_servo_command,
    format_tracking_command,
    move_toward_at_speed,
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


if __name__ == "__main__":
    unittest.main()
