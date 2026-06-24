"""Sensor platform for the Brightwheel integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import BrightwheelCoordinator

_LOGGER = logging.getLogger(__name__)


_MEAL_TYPE_LABELS = {
    1: "breakfast",
    2: "snack",
    3: "lunch",
    4: "dinner",
}


def _meal_type_label(activity: dict[str, Any]) -> str:
    blob = activity.get("details_blob") or {}
    meal_type = blob.get("food_meal_type")
    return _MEAL_TYPE_LABELS.get(meal_type, "meal")


def _actor_name(activity: dict[str, Any] | None) -> str | None:
    """Extract the actor's full name from an activity."""
    if activity is None:
        return None
    actor = activity.get("actor")
    if not actor:
        return None
    return f"{actor.get('first_name', '')} {actor.get('last_name', '')}".strip() or None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Brightwheel sensors from a config entry."""
    coordinator: BrightwheelCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []
    for student_info in coordinator.students:
        student = student_info.get("student", student_info)
        student_id = student["object_id"]
        first_name = student.get("first_name", "Unknown")

        entities.extend(
            [
                BrightwheelLastNapSensor(coordinator, student_id, first_name, entry),
                BrightwheelLastDiaperSensor(coordinator, student_id, first_name, entry),
                BrightwheelLastBottleSensor(coordinator, student_id, first_name, entry),
                BrightwheelLastMealSensor(coordinator, student_id, first_name, entry),
                BrightwheelLastCheckinSensor(coordinator, student_id, first_name, entry),
                BrightwheelLastPhotoSensor(coordinator, student_id, first_name, entry),
                BrightwheelLastMessageSensor(coordinator, student_id, first_name, entry),
                BrightwheelLastActivitySensor(coordinator, student_id, first_name, entry),
                BrightwheelActivityCountSensor(coordinator, student_id, first_name, entry),
            ]
        )

    async_add_entities(entities)


class BrightwheelSensorBase(CoordinatorEntity[BrightwheelCoordinator], SensorEntity):
    """Base class for Brightwheel sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BrightwheelCoordinator,
        student_id: str,
        first_name: str,
        entry: ConfigEntry,
        sensor_type: str,
        name_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._student_id = student_id
        self._first_name = first_name
        slug = slugify(first_name)
        self._attr_unique_id = f"{entry.entry_id}_{student_id}_{sensor_type}"
        self.entity_id = f"sensor.{slug}_{sensor_type}"
        self._attr_name = f"{first_name} {name_suffix}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._student_id)},
            name=self._first_name,
            manufacturer="Brightwheel",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def _student_data(self) -> dict[str, Any] | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._student_id)


class BrightwheelLastNapSensor(BrightwheelSensorBase):
    """Sensor for the most recent nap activity."""

    def __init__(self, coordinator, student_id, first_name, entry) -> None:
        super().__init__(
            coordinator, student_id, first_name, entry, "last_nap", "Last Nap"
        )
        self._attr_icon = "mdi:sleep"

    @property
    def native_value(self) -> str:
        data = self._student_data
        if data is None or data["last_nap"] is None:
            return "none"
        nap = data["last_nap"]
        return "sleeping" if nap.get("state") == "1" else "ended"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._student_data
        if data is None or data["last_nap"] is None:
            return {}
        nap = data["last_nap"]
        all_naps = data.get("today_naps", [])
        # Pair nap start/end events into complete nap records.
        # Activities arrive newest-first: [end2, start2, end1, start1, ...]
        nap_records = []
        i = 0
        while i < len(all_naps):
            n = all_naps[i]
            blob = n.get("details_blob") or {}
            state = blob.get("state", n.get("state", ""))
            if str(state) == "0":
                # Nap ended — look for matching start
                end_date = n.get("event_date")
                start_date = None
                if i + 1 < len(all_naps):
                    next_n = all_naps[i + 1]
                    next_blob = next_n.get("details_blob") or {}
                    next_state = next_blob.get("state", next_n.get("state", ""))
                    if str(next_state) == "1":
                        start_date = next_n.get("event_date")
                        i += 1
                nap_records.append({
                    "start": start_date,
                    "end": end_date,
                })
            else:
                # Nap still in progress (no end yet)
                nap_records.append({
                    "start": n.get("event_date"),
                    "end": None,
                })
            i += 1
        return {
            "event_date": nap.get("event_date"),
            "nap_state": nap.get("state"),
            "actor_name": _actor_name(nap),
            "action_type": nap.get("action_type"),
            "all_naps": nap_records,
            "nap_count": len(nap_records),
        }


class BrightwheelLastDiaperSensor(BrightwheelSensorBase):
    """Sensor for the most recent diaper/potty activity."""

    def __init__(self, coordinator, student_id, first_name, entry) -> None:
        super().__init__(
            coordinator, student_id, first_name, entry, "last_diaper", "Last Diaper"
        )
        self._attr_icon = "mdi:baby-bottle-outline"

    @property
    def native_value(self) -> str:
        data = self._student_data
        if data is None or data["last_diaper"] is None:
            return "none"
        diaper = data["last_diaper"]
        blob = diaper.get("details_blob") or {}
        return blob.get("potty_type", "unknown")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._student_data
        if data is None or data["last_diaper"] is None:
            return {}
        diaper = data["last_diaper"]
        blob = diaper.get("details_blob") or {}
        all_diapers = data.get("today_diapers", [])
        diaper_summaries = []
        for d in all_diapers:
            d_blob = d.get("details_blob") or {}
            diaper_summaries.append({
                "event_date": d.get("event_date"),
                "diaper_type": d_blob.get("potty_type"),
                "diaper_extras": d_blob.get("potty_extras", []),
            })
        return {
            "event_date": diaper.get("event_date"),
            "diaper_type": blob.get("potty_type"),
            "diaper_extras": blob.get("potty_extras", []),
            "actor_name": _actor_name(diaper),
            "action_type": diaper.get("action_type"),
            "all_diapers": diaper_summaries,
            "diaper_count": len(all_diapers),
        }


class BrightwheelLastBottleSensor(BrightwheelSensorBase):
    """Sensor for the most recent food/bottle activity."""

    def __init__(self, coordinator, student_id, first_name, entry) -> None:
        super().__init__(
            coordinator, student_id, first_name, entry, "last_bottle", "Last Bottle"
        )
        self._attr_icon = "mdi:baby-bottle"

    @property
    def native_value(self) -> str:
        data = self._student_data
        if data is None or data["last_bottle"] is None:
            return "none"
        bottle = data["last_bottle"]
        tags = bottle.get("menu_item_tags") or []
        items = [t.get("name", "") for t in tags if t.get("name")]
        return ", ".join(items) if items else "food"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._student_data
        if data is None or data["last_bottle"] is None:
            return {}
        bottle = data["last_bottle"]
        tags = bottle.get("menu_item_tags") or []
        blob = bottle.get("details_blob") or {}
        all_bottles = data.get("today_bottles", [])
        bottle_summaries = []
        for b in all_bottles:
            btags = b.get("menu_item_tags") or []
            b_blob = b.get("details_blob") or {}
            items = [t.get("name", "") for t in btags if t.get("name")]
            amount = b_blob.get("amount", 0)
            if amount is not None and amount < 0:
                amount = 0
            bottle_summaries.append({
                "event_date": b.get("event_date"),
                "items": items,
                "amount": amount or 0,
                "amount_type": b_blob.get("amount_type", ""),
                "food_type": b_blob.get("food_type", ""),
                "note": b.get("note"),
            })
        amount = blob.get("amount", 0)
        if amount is not None and amount < 0:
            amount = 0
        return {
            "event_date": bottle.get("event_date"),
            "food_items": [t.get("name", "") for t in tags],
            "amount": amount or 0,
            "amount_type": blob.get("amount_type", ""),
            "food_type": blob.get("food_type", ""),
            "note": bottle.get("note"),
            "actor_name": _actor_name(bottle),
            "action_type": bottle.get("action_type"),
            "all_bottles": bottle_summaries,
            "bottle_count": len(all_bottles),
        }


class BrightwheelLastCheckinSensor(BrightwheelSensorBase):
    """Sensor for the most recent check-in / check-out activity."""

    def __init__(self, coordinator, student_id, first_name, entry) -> None:
        super().__init__(
            coordinator, student_id, first_name, entry, "last_checkin", "Last Check-in"
        )
        self._attr_icon = "mdi:account-check"

    @property
    def native_value(self) -> str:
        data = self._student_data
        if data is None or data["last_checkin"] is None:
            return "none"
        checkin = data["last_checkin"]
        return "checked_in" if checkin.get("state") == "1" else "checked_out"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._student_data
        if data is None or data["last_checkin"] is None:
            return {}
        checkin = data["last_checkin"]
        return {
            "event_date": checkin.get("event_date"),
            "state": checkin.get("state"),
            "actor_name": _actor_name(checkin),
            "action_type": checkin.get("action_type"),
        }


class BrightwheelActivityCountSensor(BrightwheelSensorBase):
    """Sensor reporting the total number of activities today."""

    def __init__(self, coordinator, student_id, first_name, entry) -> None:
        super().__init__(
            coordinator,
            student_id,
            first_name,
            entry,
            "activity_count",
            "Activity Count",
        )
        self._attr_icon = "mdi:counter"

    @property
    def native_value(self) -> int:
        data = self._student_data
        if data is None:
            return 0
        return len(data.get("activities", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._student_data
        if data is None:
            return {}
        activities = data.get("activities", [])
        type_counts: dict[str, int] = {}
        for act in activities:
            atype = act.get("action_type", "unknown")
            type_counts[atype] = type_counts.get(atype, 0) + 1
        # Build a human-readable day summary
        naps = data.get("today_naps", [])
        diapers = data.get("today_diapers", [])
        meals = data.get("today_meals", [])
        bottles = data.get("today_bottles", [])
        photos = data.get("today_photos", [])
        checkin = data.get("last_checkin")

        parts = []
        if checkin:
            checkin_time = checkin.get("event_date", "")[:16].replace("T", " ")
            status = "In" if checkin.get("state") == "1" else "Out"
            parts.append(f"{status} since {checkin_time}")
        if naps:
            parts.append(f"{len(naps)} nap event(s)")
        meal_labels = [_meal_type_label(m) for m in meals]
        if meal_labels:
            parts.append(", ".join(meal_labels))
        if bottles:
            parts.append(f"{len(bottles)} bottle(s)")
        if diapers:
            parts.append(f"{len(diapers)} diaper(s)")
        if photos:
            parts.append(f"{len(photos)} photo(s)")

        return {
            "activity_type_counts": type_counts,
            "today_summary": " • ".join(parts) if parts else "No activities yet",
        }


class BrightwheelLastMealSensor(BrightwheelSensorBase):
    """Sensor for the most recent solid food meal."""

    def __init__(self, coordinator, student_id, first_name, entry) -> None:
        super().__init__(
            coordinator, student_id, first_name, entry, "last_meal", "Last Meal"
        )
        self._attr_icon = "mdi:food"

    @property
    def native_value(self) -> str:
        data = self._student_data
        if data is None or data["last_meal"] is None:
            return "none"
        meal = data["last_meal"]
        tags = meal.get("menu_item_tags") or []
        items = [t.get("name", "") for t in tags if t.get("name")]
        label = _meal_type_label(meal)
        return ", ".join(items) if items else label

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._student_data
        if data is None or data["last_meal"] is None:
            return {}
        meal = data["last_meal"]
        tags = meal.get("menu_item_tags") or []
        all_meals = data.get("today_meals", [])
        meal_summaries = []
        for m in all_meals:
            mtags = m.get("menu_item_tags") or []
            m_blob = m.get("details_blob") or {}
            items = [t.get("name", "") for t in mtags if t.get("name")]
            meal_summaries.append({
                "event_date": m.get("event_date"),
                "meal_type": _meal_type_label(m),
                "items": items,
                "food_type": m_blob.get("food_type", ""),
                "note": m.get("note"),
            })
        blob = meal.get("details_blob") or {}
        return {
            "event_date": meal.get("event_date"),
            "meal_type": _meal_type_label(meal),
            "food_items": [t.get("name", "") for t in tags],
            "food_type": blob.get("food_type", ""),
            "note": meal.get("note"),
            "actor_name": _actor_name(meal),
            "action_type": meal.get("action_type"),
            "all_meals": meal_summaries,
            "meal_count": len(all_meals),
        }


class BrightwheelLastPhotoSensor(BrightwheelSensorBase):
    """Sensor for the most recent photo or video posted."""

    def __init__(self, coordinator, student_id, first_name, entry) -> None:
        super().__init__(
            coordinator, student_id, first_name, entry, "last_photo", "Last Photo"
        )
        self._attr_icon = "mdi:camera"

    @property
    def native_value(self) -> str:
        data = self._student_data
        if data is None or data["last_photo"] is None:
            return "none"
        photo = data["last_photo"]
        note = photo.get("note") or ""
        return note[:255] if note else photo.get("action_type", "photo")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._student_data
        if data is None or data["last_photo"] is None:
            return {}
        photo = data["last_photo"]
        all_photos = data.get("today_photos", [])
        photo_summaries = []
        for p in all_photos:
            media = p.get("media") or {}
            photo_summaries.append({
                "event_date": p.get("event_date"),
                "action_type": p.get("action_type"),
                "photo_url": media.get("image_url"),
                "thumbnail_url": media.get("thumbnail_url"),
                "note": p.get("note"),
            })
        media = photo.get("media") or {}
        return {
            "event_date": photo.get("event_date"),
            "action_type": photo.get("action_type"),
            "photo_url": media.get("image_url"),
            "thumbnail_url": media.get("thumbnail_url"),
            "note": photo.get("note"),
            "actor_name": _actor_name(photo),
            "all_photos": photo_summaries,
            "photo_count": len(all_photos),
        }


class BrightwheelLastMessageSensor(BrightwheelSensorBase):
    """Sensor for the most recent teacher note, observation, or kudo."""

    def __init__(self, coordinator, student_id, first_name, entry) -> None:
        super().__init__(
            coordinator, student_id, first_name, entry, "last_message", "Last Message"
        )
        self._attr_icon = "mdi:message-text"

    @property
    def native_value(self) -> str:
        data = self._student_data
        if data is None or data["last_message"] is None:
            return "none"
        msg = data["last_message"]
        note = msg.get("note") or ""
        return note[:255] if note else msg.get("action_type", "message")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._student_data
        if data is None or data["last_message"] is None:
            return {}
        msg = data["last_message"]
        all_messages = data.get("today_messages", [])
        message_summaries = []
        for m in all_messages:
            message_summaries.append({
                "event_date": m.get("event_date"),
                "action_type": m.get("action_type"),
                "note": m.get("note"),
                "actor_name": _actor_name(m),
            })
        return {
            "event_date": msg.get("event_date"),
            "action_type": msg.get("action_type"),
            "note": msg.get("note"),
            "actor_name": _actor_name(msg),
            "all_messages": message_summaries,
            "message_count": len(all_messages),
        }


_ACTIVITY_LABELS: dict[str, str] = {
    "ac_nap": "Nap",
    "ac_potty": "Diaper",
    "ac_food": "Meal",
    "ac_checkin": "Check-in",
    "ac_photo": "Photo",
    "ac_video": "Video",
    "ac_note": "Note",
    "ac_observation": "Observation",
    "ac_kudo": "Kudo",
}


def _activity_description(activity: dict[str, Any]) -> str:
    """Return a short human-readable description of any activity."""
    action = activity.get("action_type", "")
    label = _ACTIVITY_LABELS.get(action, action)

    if action == "ac_nap":
        state = activity.get("state", "")
        return f"Nap {'started' if str(state) == '1' else 'ended'}"

    if action == "ac_potty":
        blob = activity.get("details_blob") or {}
        potty_type = blob.get("potty_type", "diaper")
        extras = blob.get("potty_extras", [])
        detail = ", ".join(extras) if extras else potty_type
        return f"Diaper: {detail}"

    if action == "ac_food":
        blob = activity.get("details_blob") or {}
        food_type = blob.get("food_type", "")
        if food_type == "bottle":
            amount = blob.get("amount") or 0
            unit = blob.get("amount_type", "oz")
            return f"Bottle: {amount} {unit}" if amount else "Bottle"
        meal_label = _meal_type_label(activity)
        tags = activity.get("menu_item_tags") or []
        items = [t.get("name", "") for t in tags if t.get("name")]
        return f"{meal_label.capitalize()}: {', '.join(items)}" if items else meal_label.capitalize()

    if action == "ac_checkin":
        state = activity.get("state", "")
        return "Checked in" if str(state) == "1" else "Checked out"

    if action in ("ac_photo", "ac_video"):
        note = activity.get("note") or ""
        return f"Photo: {note[:80]}" if note else "Photo posted"

    note = activity.get("note") or ""
    return f"{label}: {note[:80]}" if note else label


class BrightwheelLastActivitySensor(BrightwheelSensorBase):
    """Sensor showing the most recent activity of any type."""

    def __init__(self, coordinator, student_id, first_name, entry) -> None:
        super().__init__(
            coordinator, student_id, first_name, entry, "last_activity", "Last Activity"
        )
        self._attr_icon = "mdi:timeline-clock"

    @property
    def native_value(self) -> str:
        data = self._student_data
        if data is None:
            return "none"
        activities = data.get("activities", [])
        if not activities:
            return "none"
        return _activity_description(activities[0])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._student_data
        if data is None:
            return {}
        activities = data.get("activities", [])
        if not activities:
            return {}
        last = activities[0]
        media = last.get("media") or {}
        return {
            "event_date": last.get("event_date"),
            "action_type": last.get("action_type"),
            "actor_name": _actor_name(last),
            "note": last.get("note"),
            "photo_url": media.get("image_url"),
            "thumbnail_url": media.get("thumbnail_url"),
        }
