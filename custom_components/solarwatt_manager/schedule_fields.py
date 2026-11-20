from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)

_MODE_TO_API = {
    "on": "BATTERY_CHARGE",
    "off": "BATTERY_HOLD_CURRENT_SOC",
}
_MODE_FROM_API = {mode: state for state, mode in _MODE_TO_API.items()}
_INTERVAL_PATTERN = re.compile(
    r"(on|off)?(\d{1,2})(?::(\d{2}))?-(\d{1,2})(?::(\d{2}))?(on|off)?",
    re.IGNORECASE,
)


def _minutes(hour: str, minute: str | None, *, allow_end_of_day: bool = False) -> int:
    hours = int(hour)
    minutes = int(minute or 0)
    if minutes > 59 or hours > 24 or (hours == 24 and (minutes or not allow_end_of_day)):
        raise ValueError(f"Invalid schedule time: {hour}:{minute or '00'}")
    return hours * 60 + minutes


def parse_day_schedule(value: str) -> list[dict[str, Any]]:
    """Convert `off14:30-18;on20-22` into KiwiGrid schedule entries."""
    if not value.strip():
        return []

    entries: list[dict[str, Any]] = []
    previous_end = -1
    compact_value = re.sub(r"\s+", "", value)
    for raw_interval in compact_value.split(";"):
        interval = raw_interval
        match = _INTERVAL_PATTERN.fullmatch(interval)
        if match is None:
            raise ValueError(f"Invalid schedule interval: {interval}")
        prefix_state, start_hour, start_minute, end_hour, end_minute, suffix_state = match.groups()
        if prefix_state and suffix_state:
            raise ValueError("Each schedule interval must contain either on or off, not both")
        state = prefix_state or suffix_state
        if state is None:
            raise ValueError("Each schedule interval must contain on or off")
        start = _minutes(start_hour, start_minute)
        end = _minutes(end_hour, end_minute, allow_end_of_day=True)
        if start >= end:
            raise ValueError("Schedule interval start must be before its end")
        if start < previous_end:
            raise ValueError("Schedule intervals must not overlap and must be ordered")
        previous_end = end
        entries.append({
            "start": f"{start // 60:02d}:{start % 60:02d}",
            "end": f"{end // 60:02d}:{end % 60:02d}",
            "mode": _MODE_TO_API[state.lower()],
            "isUserSchedule": True,
        })
    return entries


def format_day_schedule(entries: Any) -> str:
    """Convert known KiwiGrid battery modes into the compact daily text format."""
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        return ""
    formatted: list[str] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        state = _MODE_FROM_API.get(str(entry.get("mode") or "").upper())
        if state is None:
            continue
        start = _format_time(entry.get("start"))
        end = _format_time(entry.get("end"))
        if start is not None and end is not None:
            formatted.append(f"{state}{start}-{end}")
    return ";".join(formatted)


def schedule_to_day_inputs(schedule: Any) -> dict[str, str]:
    """Return all seven editable daily strings for a GET schedule response."""
    if not isinstance(schedule, Mapping):
        raise ValueError("Battery schedule response must be an object")
    return {day: format_day_schedule(schedule.get(day, [])) for day in WEEKDAYS}


def day_inputs_to_schedule(day_inputs: Mapping[str, str]) -> dict[str, list[dict[str, Any]]]:
    """Build the weekday-keyed API schedule from the seven text fields."""
    if not any(str(day_inputs.get(day, "")).strip() for day in WEEKDAYS):
        return {}
    return {day: parse_day_schedule(str(day_inputs.get(day, ""))) for day in WEEKDAYS}


def _format_time(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", value)
    if match is None:
        return None
    minutes = _minutes(match.group(1), match.group(2), allow_end_of_day=True)
    if minutes == 24 * 60:
        return "24:00"
    return f"{minutes // 60:02d}:{minutes % 60:02d}"