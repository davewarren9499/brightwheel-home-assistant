"""Binary sensor platform for the Brightwheel integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import BrightwheelCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Brightwheel binary sensors from a config entry."""
    coordinator: BrightwheelCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for student_info in coordinator.students:
        student = student_info.get("student", student_info)
        student_id = student["object_id"]
        first_name = student.get("first_name", "Unknown")
        entities.append(BrightwheelAtSchoolSensor(coordinator, student_id, first_name, entry))

    async_add_entities(entities)


class BrightwheelAtSchoolSensor(CoordinatorEntity[BrightwheelCoordinator], BinarySensorEntity):
    """Binary sensor that is ON when the child is checked in at school."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PRESENCE
    _attr_icon = "mdi:school"

    def __init__(
        self,
        coordinator: BrightwheelCoordinator,
        student_id: str,
        first_name: str,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._student_id = student_id
        self._first_name = first_name
        slug = slugify(first_name)
        self._attr_unique_id = f"{entry.entry_id}_{student_id}_at_school"
        self.entity_id = f"binary_sensor.{slug}_at_school"
        self._attr_name = f"{first_name} At School"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._student_id)},
            name=self._first_name,
            manufacturer="Brightwheel",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def is_on(self) -> bool:
        if self.coordinator.data is None:
            return False
        data = self.coordinator.data.get(self._student_id)
        if data is None or data["last_checkin"] is None:
            return False
        return data["last_checkin"].get("state") == "1"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.coordinator.data is None:
            return {}
        data = self.coordinator.data.get(self._student_id)
        if data is None or data["last_checkin"] is None:
            return {}
        checkin = data["last_checkin"]
        return {
            "event_date": checkin.get("event_date"),
            "actor_name": f"{checkin.get('actor', {}).get('first_name', '')} {checkin.get('actor', {}).get('last_name', '')}".strip(),
        }
