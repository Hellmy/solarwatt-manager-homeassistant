from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    SOLARWATTConfigEntry,
    build_thing_device_info,
    get_device_registry_anchor,
    get_selected_thing_uids,
)
from .entity_helpers import (
    build_thing_diagnostics_refresh_unique_id,
    collect_new_thing_entities,
    build_thing_override_reset_unique_id,
    build_thing_config_reset_unique_id,
    has_optimization_defaults,
    build_thing_schedule_refresh_unique_id,
    build_thing_schedule_set_unique_id,
    build_thing_schedule_fields_clear_unique_id,
    is_hems_battery_thing,
    is_hems_switchable_thing,
    setup_hems_control_entities,
)
from .schedule_fields import WEEKDAYS, day_inputs_to_schedule, schedule_to_day_inputs


async def async_setup_entry(
    hass: HomeAssistant, entry: SOLARWATTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    setup_hems_control_entities(
        entry, async_add_entities, is_hems_switchable_thing,
        lambda uid, thing, device_id, selected: SOLARWATTOverrideResetButton(
            entry.runtime_data, entry.entry_id, uid, thing, device_id, selected,
        ),
    )
    setup_hems_control_entities(
        entry, async_add_entities, has_optimization_defaults,
        lambda uid, thing, device_id, selected: SOLARWATTConfigResetButton(
            entry.runtime_data, entry.entry_id, uid, thing, device_id, selected,
        ),
    )
    setup_hems_control_entities(
        entry, async_add_entities, is_hems_battery_thing,
        lambda uid, thing, device_id, selected: SOLARWATTScheduleRefreshButton(
            entry.runtime_data, entry.entry_id, uid, thing, device_id, selected,
        ),
    )
    setup_hems_control_entities(
        entry, async_add_entities, is_hems_battery_thing,
        lambda uid, thing, device_id, selected: SOLARWATTScheduleSetButton(
            entry.runtime_data, entry.entry_id, uid, thing, device_id, selected,
        ),
    )
    setup_hems_control_entities(
        entry, async_add_entities, is_hems_battery_thing,
        lambda uid, thing, device_id, selected: SOLARWATTScheduleFieldsClearButton(
            entry.runtime_data, entry.entry_id, uid, thing, device_id, selected,
        ),
    )
    coordinator = entry.runtime_data
    added_diagnostics_thing_uids: set[str] = set()

    @callback
    def _async_discover_new_entities(options: Mapping[str, Any] | None = None) -> None:
        selected_thing_uids = get_selected_thing_uids(
            options if options is not None else entry.options
        )
        new_entities: list[ButtonEntity] = collect_new_thing_entities(
            coordinator.things,
            selected_thing_uids,
            added_diagnostics_thing_uids,
            lambda thing_uid, thing: SOLARWATTDiagnosticsRefreshButton(
                coordinator,
                entry.entry_id,
                thing_uid,
                thing,
                selected_thing_uids,
            ),
        )
        if new_entities:
            async_add_entities(new_entities)

    _async_discover_new_entities()
    entry.async_on_unload(coordinator.register_discovery_callback(_async_discover_new_entities))


class SOLARWATTDiagnosticsRefreshButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "diagnostics_refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator,
        entry_id: str,
        thing_uid: str,
        thing: dict,
        selected_thing_uids: set[str] | None,
    ):
        super().__init__(coordinator)
        self._thing_uid = thing_uid
        self._attr_unique_id = build_thing_diagnostics_refresh_unique_id(entry_id, thing_uid)
        self._attr_device_info = build_thing_device_info(
            self.coordinator.hass,
            get_device_registry_anchor(self.coordinator.entry),
            thing,
            self.coordinator.things,
            selected_thing_uids,
            str(self.coordinator.client.host or ""),
            config_entry_id=entry_id,
        )

    async def async_press(self) -> None:
        self.coordinator.invalidate_hems_cache()
        await self.coordinator.async_refresh_discovery_data()
        await self.coordinator.async_request_refresh()


class SOLARWATTScheduleRefreshButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "schedule_refresh"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:calendar-refresh"

    def __init__(self, coordinator, entry_id, thing_uid, thing, device_id, selected):
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = build_thing_schedule_refresh_unique_id(entry_id, thing_uid)
        self._attr_device_info = build_thing_device_info(
            coordinator.hass,
            get_device_registry_anchor(coordinator.entry),
            thing,
            coordinator.things,
            selected,
            str(coordinator.client.host or ""),
            config_entry_id=entry_id,
        )

    async def async_press(self) -> None:
        try:
            await self.coordinator.async_get_hems_device_schedule(self._device_id)
        except Exception as err:
            raise HomeAssistantError(f"Unable to fetch KiwiGrid HEMS schedule: {err}") from err


class SOLARWATTScheduleSetButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "schedule_set"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator, entry_id, thing_uid, thing, device_id, selected):
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = build_thing_schedule_set_unique_id(entry_id, thing_uid)
        self._attr_device_info = build_thing_device_info(
            coordinator.hass,
            get_device_registry_anchor(coordinator.entry),
            thing,
            coordinator.things,
            selected,
            str(coordinator.client.host or ""),
            config_entry_id=entry_id,
        )

    async def async_press(self) -> None:
        schedule = getattr(self.coordinator, "hems_schedules", {}).get(self._device_id)
        if schedule is None:
            raise HomeAssistantError("Get the schedule before sending it")
        try:
            day_inputs = getattr(self.coordinator, "hems_schedule_day_inputs", {}).get(
                self._device_id,
                schedule_to_day_inputs(schedule),
            )
            edited_schedule = day_inputs_to_schedule(day_inputs)
            await self.coordinator.async_set_hems_device_schedule(
                self._device_id,
                edited_schedule,
            )
        except Exception as err:
            raise HomeAssistantError(f"Unable to set KiwiGrid HEMS schedule: {err}") from err


class SOLARWATTScheduleFieldsClearButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "schedule_fields_clear"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:playlist-remove"

    def __init__(self, coordinator, entry_id, thing_uid, thing, device_id, selected):
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = build_thing_schedule_fields_clear_unique_id(entry_id, thing_uid)
        self._attr_device_info = build_thing_device_info(
            coordinator.hass,
            get_device_registry_anchor(coordinator.entry),
            thing,
            coordinator.things,
            selected,
            str(coordinator.client.host or ""),
            config_entry_id=entry_id,
        )

    async def async_press(self) -> None:
        self.coordinator.hems_schedule_day_inputs[self._device_id] = {
            day: "" for day in WEEKDAYS
        }
        self.coordinator.async_update_listeners()


class SOLARWATTOverrideResetButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "override_reset"
    _attr_icon = "mdi:restore"

    def __init__(
        self,
        coordinator,
        entry_id: str,
        thing_uid: str,
        thing: dict[str, Any],
        device_id: str,
        selected: set[str] | None,
    ) -> None:
        super().__init__(coordinator)
        self._hems_device_id = device_id
        self._attr_unique_id = build_thing_override_reset_unique_id(entry_id, thing_uid)
        self._attr_device_info = build_thing_device_info(
            coordinator.hass, get_device_registry_anchor(coordinator.entry),
            thing, coordinator.things, selected, str(coordinator.client.host or ""),
            config_entry_id=entry_id,
        )

    async def async_press(self) -> None:
        try:
            await self.coordinator.async_clear_hems_device_optimization_state(self._hems_device_id)
        except Exception as err:
            raise HomeAssistantError(f"Unable to reset KiwiGrid HEMS override: {err}") from err


class SOLARWATTConfigResetButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "optimization_config_reset"
    _attr_icon = "mdi:restore"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator, entry_id: str, thing_uid: str, thing: dict[str, Any],
        device_id: str, selected: set[str] | None,
    ) -> None:
        super().__init__(coordinator)
        self._thing_uid = thing_uid
        self._hems_device_id = device_id
        self._attr_unique_id = build_thing_config_reset_unique_id(entry_id, thing_uid)
        self._attr_device_info = build_thing_device_info(
            coordinator.hass, get_device_registry_anchor(coordinator.entry),
            thing, coordinator.things, selected, str(coordinator.client.host or ""),
            config_entry_id=entry_id,
        )

    @property
    def available(self) -> bool:
        thing = self.coordinator.things.get(self._thing_uid, {})
        props = thing.get("properties", {})
        return super().available and props.get("optimizationResetAvailable") == "true"

    async def async_press(self) -> None:
        try:
            await self.coordinator.async_reset_hems_device_optimization_config(self._hems_device_id)
        except Exception as err:
            raise HomeAssistantError(f"Unable to reset optimization settings: {err}") from err
