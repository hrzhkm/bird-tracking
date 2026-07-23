import unittest

from bird_tracker.prediction import LostTargetRecovery


def make_predictor(**overrides):
    settings = {
        "velocity_tau": 0.0,
        "coast_seconds": 0.6,
        "search_seconds": 1.2,
        "minimum_speed": 0.12,
        "maximum_speed": 2.0,
        "edge_zone": 0.2,
        "search_error": 0.3,
        "prediction_margin": 0.2,
    }
    settings.update(overrides)
    return LostTargetRecovery(**settings)


class LostTargetRecoveryTests(unittest.TestCase):
    def test_coasts_along_recent_screen_velocity(self):
        predictor = make_predictor()
        predictor.observe(0.5, 0.5, 0.0, identity=7)
        predictor.observe(0.7, 0.5, 0.1, identity=7)

        error_x, error_y, mode = predictor.predict(0.2)

        self.assertEqual(mode, "coast")
        self.assertAlmostEqual(error_x, 0.4)
        self.assertAlmostEqual(error_y, 0.0)

    def test_stationary_target_does_not_trigger_recovery(self):
        predictor = make_predictor()
        predictor.observe(0.5, 0.5, 0.0)
        predictor.observe(0.505, 0.5, 0.1)

        self.assertIsNone(predictor.predict(0.2))

    def test_searches_only_toward_a_likely_exit_edge(self):
        predictor = make_predictor()
        predictor.observe(0.65, 0.5, 0.0)
        predictor.observe(0.85, 0.5, 0.1)

        error_x, error_y, mode = predictor.predict(0.8)

        self.assertEqual(mode, "search")
        self.assertEqual(error_x, 0.3)
        self.assertEqual(error_y, 0.0)

    def test_does_not_search_when_motion_did_not_approach_an_edge(self):
        predictor = make_predictor(coast_seconds=0.1)
        predictor.observe(0.4, 0.5, 0.0)
        predictor.observe(0.45, 0.5, 0.1)

        self.assertIsNone(predictor.predict(0.3))

    def test_recovery_expires(self):
        predictor = make_predictor()
        predictor.observe(0.5, 0.5, 0.0)
        predictor.observe(0.8, 0.5, 0.1)

        self.assertIsNone(predictor.predict(2.0))

    def test_identity_change_discards_previous_velocity(self):
        predictor = make_predictor()
        predictor.observe(0.2, 0.5, 0.0, identity=1)
        predictor.observe(0.8, 0.5, 0.1, identity=2)

        self.assertIsNone(predictor.predict(0.2))

    def test_coast_target_is_bounded_outside_frame(self):
        predictor = make_predictor()
        predictor.observe(0.7, 0.5, 0.0)
        predictor.observe(0.9, 0.5, 0.1)

        error_x, _, _ = predictor.predict(0.6)

        self.assertEqual(error_x, 0.7)


if __name__ == "__main__":
    unittest.main()
