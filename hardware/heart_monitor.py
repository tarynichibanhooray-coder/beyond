"""Placeholder: connect Polar/USB sensor and yield (timestamp, bpm)."""


class HeartRateMonitor:
    def __init__(self) -> None:
        self.bpm_history: list[tuple[float, float]] = []

    def get_current_bpm(self) -> float:
        return 72.0
