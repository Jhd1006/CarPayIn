from datetime import datetime


class SimpleFeeCalculator:
    def __init__(self, *, amount_per_30_minutes: int = 500) -> None:
        self._amount_per_30_minutes = amount_per_30_minutes

    def calculate(self, entry_time: str, current_time: str) -> dict:
        entry = datetime.fromisoformat(entry_time)
        current = datetime.fromisoformat(current_time)
        duration_minutes = int((current - entry).total_seconds() / 60)
        if duration_minutes < 0:
            raise ValueError("invalid_current_time")

        blocks = (duration_minutes + 29) // 30
        return {
            "amount": blocks * self._amount_per_30_minutes,
            "duration_minutes": duration_minutes,
        }
