from bird_tracker.targeting import choose_target, is_tracking_target


def test_only_configured_labels_are_targets():
    allowed = ("bird", "monkey")
    assert is_tracking_target("bird", 0.8, allowed, 0.2)
    assert is_tracking_target("monkey", 0.8, allowed, 0.2)
    assert not is_tracking_target("human", 0.8, allowed, 0.2)
    assert not is_tracking_target("bird", 0.2, allowed, 0.2)


def test_active_track_wins_then_nearest_target_is_selected():
    bird = (0.1, 0.1, None, 0.8, 10, 0, "bird")
    monkey = (0.6, 0.6, None, 0.9, 20, 2, "monkey")

    assert choose_target([bird, monkey], 10, 0.5, 0.5) is bird
    assert choose_target([bird, monkey], None, 0.5, 0.5) is monkey
    assert choose_target([], None, 0.5, 0.5) is None
