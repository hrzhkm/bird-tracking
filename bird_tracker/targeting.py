"""Pure target filtering and selection helpers."""


def is_tracking_target(label, confidence, allowed_labels, threshold):
    return label in allowed_labels and confidence > threshold


def choose_target(targets, active_track_id, aim_x, aim_y):
    if not targets:
        return None
    candidates = (
        [target for target in targets if target[4] == active_track_id]
        if active_track_id is not None
        else targets
    )
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda target: (
            (target[0] - aim_x) ** 2 + (target[1] - aim_y) ** 2
        ),
    )
