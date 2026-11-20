from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from .module_loader import load_component_module_with_stubs, make_module


@pytest.fixture
def schedule_services():
    package = "solarwatt_schedule_service_test"

    class HomeAssistantError(Exception):
        pass

    class SolarwattError(Exception):
        pass

    class ScheduleSensor:
        pass

    class StatsTotalSensor:
        pass

    return load_component_module_with_stubs(
        "services",
        package_name=package,
        stubs={
            "homeassistant": make_module("homeassistant"),
            "homeassistant.const": make_module(
                "homeassistant.const", CONF_ENTITY_ID="entity_id"
            ),
            "homeassistant.core": make_module(
                "homeassistant.core", HomeAssistant=object, ServiceCall=object
            ),
            "homeassistant.exceptions": make_module(
                "homeassistant.exceptions", HomeAssistantError=HomeAssistantError
            ),
            "homeassistant.helpers.config_validation": make_module(
                "homeassistant.helpers.config_validation",
                entity_ids=lambda value: value,
            ),
            "homeassistant.helpers": make_module("homeassistant.helpers"),
            f"{package}.client": make_module(
                f"{package}.client", SolarwattError=SolarwattError
            ),
            f"{package}.const": make_module(
                f"{package}.const", DOMAIN="solarwatt_manager"
            ),
            f"{package}.sensor": make_module(
                f"{package}.sensor",
                HEMS_SCHEDULE_ENTITY_MAP="hems_schedule_entities",
                STATS_TOTAL_ENTITY_MAP="stats_total_entities",
                SOLARWATTScheduleSensor=ScheduleSensor,
                SOLARWATTStatsTotalSensor=StatsTotalSensor,
            ),
        },
    )


def _registered_service(schedule_services):
    handlers = {}
    hass = SimpleNamespace(
        data={},
        services=SimpleNamespace(
            async_register=lambda domain, service, handler, schema=None: (
                handlers.update({service: handler})
            )
        ),
    )
    schedule_services.async_register_services(hass)
    return hass, handlers[schedule_services.SERVICE_SET_DEVICE_SCHEDULE]


def test_set_schedule_service_targets_one_battery_sensor(schedule_services):
    hass, handler = _registered_service(schedule_services)
    sensor = schedule_services.SOLARWATTScheduleSensor()
    sensor.device_id = "battery-id"
    sensor.coordinator = SimpleNamespace(
        async_set_hems_device_schedule=AsyncMock(),
        hems_schedules={"battery-id": {"schedule": [{"start": "07:00"}]}},
    )
    hass.data["solarwatt_manager"] = {
        "hems_schedule_entities": {"sensor.battery_schedule": sensor}
    }
    schedule = {"schedule": [{"start": "08:00"}]}

    asyncio.run(
        handler(
            SimpleNamespace(
                data={"entity_id": ["sensor.battery_schedule"], "schedule": schedule}
            )
        )
    )

    sensor.coordinator.async_set_hems_device_schedule.assert_awaited_once_with(
        "battery-id", schedule
    )


def test_set_schedule_service_uses_cached_get_response(schedule_services):
    hass, handler = _registered_service(schedule_services)
    sensor = schedule_services.SOLARWATTScheduleSensor()
    sensor.device_id = "battery-id"
    cached_schedule = {"schedule": [{"start": "08:00", "enabled": True}]}
    sensor.coordinator = SimpleNamespace(
        async_set_hems_device_schedule=AsyncMock(),
        hems_schedules={"battery-id": cached_schedule},
    )
    hass.data["solarwatt_manager"] = {
        "hems_schedule_entities": {"sensor.battery_schedule": sensor}
    }

    asyncio.run(
        handler(SimpleNamespace(data={"entity_id": ["sensor.battery_schedule"]}))
    )

    sensor.coordinator.async_set_hems_device_schedule.assert_awaited_once_with(
        "battery-id", cached_schedule
    )


def test_set_schedule_service_requires_get_or_explicit_json(schedule_services):
    hass, handler = _registered_service(schedule_services)
    sensor = schedule_services.SOLARWATTScheduleSensor()
    sensor.device_id = "battery-id"
    sensor.coordinator = SimpleNamespace(
        async_set_hems_device_schedule=AsyncMock(),
        hems_schedules={},
    )
    hass.data["solarwatt_manager"] = {
        "hems_schedule_entities": {"sensor.battery_schedule": sensor}
    }

    with pytest.raises(schedule_services.HomeAssistantError, match="Fetch the schedule first"):
        asyncio.run(
            handler(SimpleNamespace(data={"entity_id": ["sensor.battery_schedule"]}))
        )
    sensor.coordinator.async_set_hems_device_schedule.assert_not_awaited()


def test_set_schedule_service_rejects_multiple_targets(schedule_services):
    _, handler = _registered_service(schedule_services)

    with pytest.raises(schedule_services.HomeAssistantError, match="exactly one"):
        asyncio.run(
            handler(
                SimpleNamespace(
                    data={"entity_id": ["sensor.one", "sensor.two"], "schedule": {}}
                )
            )
        )
