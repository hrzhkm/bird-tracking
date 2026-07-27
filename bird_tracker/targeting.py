"""Pure target filtering and selection helpers."""


def is_tracking_target(label, confidence, allowed_labels, threshold):
    return label in allowed_labels and confidence > threshold


def choose_target(targets, active_track_id, aim_x, aim_y):
    if not targets:
        return None
    matching = [
        target
        for target in targets
        if active_track_id is not None and target[4] == active_track_id
    ]
    return min(
        matching or targets,
        key=lambda target: (
            (target[0] - aim_x) ** 2 + (target[1] - aim_y) ** 2
        ),
    )
