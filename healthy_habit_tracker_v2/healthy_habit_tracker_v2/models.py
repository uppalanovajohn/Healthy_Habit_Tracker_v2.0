from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

HABIT_RULES: Dict[str, Dict[str, Any]] = {
    "reading": {"unit": "minutes", "min": 1.0, "max": 600.0, "daily_goal": 30.0},
    "exercise": {"unit": "minutes", "min": 1.0, "max": 360.0, "daily_goal": 45.0},
    "hydration": {"unit": "glasses", "min": 1.0, "max": 25.0, "daily_goal": 8.0},
}

@dataclass
class HabitRecord:
    date: str
    category: str
    value: float
    notes: str = ""
    record_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if data["record_id"] is None:
            data.pop("record_id")
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HabitRecord":
        return cls(
            date=str(data["date"]).strip(),
            category=str(data["category"]).strip().lower(),
            value=float(data["value"]),
            notes=str(data.get("notes", "")).strip(),
            record_id=data.get("record_id"),
        )
