from datetime import datetime, timezone


class SimpleFeeCalculator:
    def __init__(self, *, amount_per_30_minutes: int = 500) -> None:
        self._amount_per_30_minutes = amount_per_30_minutes

    def calculate(self, entry_time: str, current_time: str) -> dict:
        entry = datetime.fromisoformat(entry_time)
        current = datetime.fromisoformat(current_time)
        # naive/aware 혼합 방지: 한쪽만 timezone 없으면 UTC로 간주
        if entry.tzinfo is not None and current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        elif entry.tzinfo is None and current.tzinfo is not None:
            entry = entry.replace(tzinfo=timezone.utc)
        duration_minutes = int((current - entry).total_seconds() / 60)
        if duration_minutes < 0:
            raise ValueError("invalid_current_time")

        blocks = (duration_minutes + 29) // 30
        return {
            "amount": blocks * self._amount_per_30_minutes,
            "duration_minutes": duration_minutes,
        }
