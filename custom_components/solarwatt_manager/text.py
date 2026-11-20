from __future__ import annotations

from functools import partial

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import SOLARWATTConfigEntry, build_thing_device_info, get_device_registry_anchor
from .entity_helpers import (
    build_thing_schedule_day_unique_id,
    is_hems_battery_thing,
    setup_hems_control_entities,
)
from .schedule_fields import WEEKDAYS, parse_day_schedule, schedule_to_day_inputs


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SOLARWATTConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    for day in WEEKDAYS:
        setup_hems_control_entities(
            entry,
            async_add_entities,
            is_hems_battery_thing,
            partial(_build_schedule_text, entry, day=day),
        )


def _build_schedule_text(entry, thing_uid, thing, device_id, selected, *, day: str):
    return SOLARWATTScheduleDayText(
        entry.runtime_data,
        entry.entry_id,
        thing_uid,
        thing,
        device_id,
        selected,
        day,
    )


class SOLARWATTScheduleDayText(CoordinatorEntity, TextEntity):
    _attr_has_entity_name = True
    _attr_native_min = 0
    _attr_native_max = 255
    _attr_mode = TextMode.TEXT
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry_id, thing_uid, thing, device_id, selected, day):
        super().__init__(coordinator)
        self._device_id = device_id
        self._day = day
        self._attr_translation_key = f"schedule_{day}"
        self._attr_unique_id = build_thing_schedule_day_unique_id(entry_id, thing_uid, day)
        self._attr_device_info = build_thing_device_info(
            coordinator.hass,
            get_device_registry_anchor(coordinator.entry),
            thing,
            coordinator.things,
            selected,
            str(coordinator.client.host or ""),
            config_entry_id=entry_id,
        )

    @property
    def native_value(self) -> str:
        day_inputs = self.coordinator.hems_schedule_day_inputs.get(self._device_id)
        if day_inputs is None:
            schedule = self.coordinator.hems_schedules.get(self._device_id)
            if schedule is None:
                return ""
            day_inputs = schedule_to_day_inputs(schedule)
        return day_inputs.get(self._day, "")

    async def async_set_value(self, value: str) -> None:
        try:
            parse_day_schedule(value)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        if len(value) > self._attr_native_max:
            raise HomeAssistantError("Daily schedule is too long")
        self.coordinator.hems_schedule_day_inputs.setdefault(self._device_id, {})[
            self._day
        ] = value.strip()
        self.coordinator.async_update_listeners()