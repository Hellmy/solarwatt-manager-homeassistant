from __future__ import annotations

import pytest

from .module_loader import load_component_module

schedule_fields = load_component_module("schedule_fields")


def test_day_schedule_parses_multiple_on_off_intervals():
    assert schedule_fields.parse_day_schedule("off14:30-18;on20-22") == [
        {
            "start": "14:30",
            "end": "18:00",
            "mode": "BATTERY_HOLD_CURRENT_SOC",
            "isUserSchedule": True,
        },
        {
            "start": "20:00",
            "end": "22:00",
            "mode": "BATTERY_CHARGE",
            "isUserSchedule": True,
        },
    ]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("off 14:30 - 18 ; on 20 - 22", "off14:30-18:00;on20:00-22:00"),
        ("14:30 - 18 off; 20 - 22 on", "off14:30-18:00;on20:00-22:00"),
        ("  14:30-18OFF ; ON20-22  ", "off14:30-18:00;on20:00-22:00"),
    ],
)
def test_day_schedule_accepts_mode_before_or_after_and_ignores_whitespace(value, expected):
    entries = schedule_fields.parse_day_schedule(value)
    assert schedule_fields.format_day_schedule(entries) == expected


def test_schedule_get_format_round_trip_and_empty_reset():
    api_schedule = {
        "wednesday": [
            {
                "start": "08:30",
                "end": "09:30",
                "mode": "BATTERY_CHARGE",
                "isUserSchedule": True,
            },
            {
                "start": "12:30",
                "end": "13:30",
                "mode": "BATTERY_HOLD_CURRENT_SOC",
                "isUserSchedule": True,
            },
        ]
    }

    fields = schedule_fields.schedule_to_day_inputs(api_schedule)
    assert fields == {
        day: "" for day in schedule_fields.WEEKDAYS if day != "wednesday"
    } | {"wednesday": "on08:30-09:30;off12:30-13:30"}
    assert schedule_fields.day_inputs_to_schedule(fields) == {
        day: schedule_fields.parse_day_schedule(fields[day])
        for day in schedule_fields.WEEKDAYS
    }
    assert schedule_fields.day_inputs_to_schedule(
        {day: "" for day in schedule_fields.WEEKDAYS}
    ) == {}


@pytest.mark.parametrize(
    "value",
    [
        "maybe08-09",
        "08-09",
        "on08-09off",
        "on24-25",
        "on12:75-13",
        "on14-15;off14:30-16",
        "on18-17",
    ],
)
def test_invalid_schedule_intervals_are_rejected(value):
    with pytest.raises(ValueError):
        schedule_fields.parse_day_schedule(value)
