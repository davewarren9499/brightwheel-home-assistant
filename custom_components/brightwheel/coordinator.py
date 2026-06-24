"""DataUpdateCoordinator for Brightwheel."""

import logging
from datetime import date, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BrightwheelClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _is_bottle(activity: dict) -> bool:
    """Return True if a Brightwheel ac_food activity is a bottle, not solid food."""
    blob = activity.get("details_blob") or {}
    food_type = blob.get("food_type", "")
    if food_type == "bottle":
        return True
    if food_type == "food":
        return False
    # food_type missing — fall back to keyword matching in the note
    note = (activity.get("note") or "").lower()
    keywords = {"bottle", "formula", "breast milk", "breastmilk", "oz", "ml"}
    return any(kw in note for kw in keywords)


def _extract_bottle_info(activity: dict) -> dict:
    """Extract bottle amount and type from a Brightwheel food activity."""
    blob = activity.get("details_blob") or {}
    amount = blob.get("amount", 0)
    if amount is not None and amount < 0:
        amount = 0
    amount_type = blob.get("amount_type", "")
    return {
        "amount": amount or 0,
        "amount_type": amount_type,
        "food_type": blob.get("food_type", ""),
    }


class BrightwheelCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and cache Brightwheel activity data."""

    def __init__(self, hass: HomeAssistant, client: BrightwheelClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.students: list[dict[str, Any]] = []

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch today's activities for every student."""
        try:
            if not self.students:
                self.students = await self.client.get_students()
                _LOGGER.debug(
                    "Brightwheel found %d students: %s",
                    len(self.students),
                    [s.get("student", s).get("first_name", "?") for s in self.students],
                )

            if not self.students:
                _LOGGER.warning("Brightwheel: no students found for this account")
                return {}

            data: dict[str, Any] = {}

            for student_info in self.students:
                student = student_info.get("student", student_info)
                student_id = student["object_id"]
                # end_date must be tomorrow because the API treats it as exclusive.
                end_date = date.today() + timedelta(days=1)
                start_date = end_date - timedelta(days=8)
                activities = await self.client.get_activities(
                    student_id,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                )
                _LOGGER.debug(
                    "Brightwheel: %s has %d activities",
                    student.get("first_name", student_id),
                    len(activities),
                )

                data[student_id] = {
                    "student": student,
                    "activities": activities,
                    "last_nap": None,
                    "last_diaper": None,
                    "last_bottle": None,
                    "last_meal": None,
                    "last_checkin": None,
                    "last_photo": None,
                    "last_message": None,
                    "today_bottles": [],
                    "today_meals": [],
                    "today_naps": [],
                    "today_diapers": [],
                    "today_photos": [],
                    "today_messages": [],
                }

                # Activities arrive newest-first
                for activity in activities:
                    action = activity.get("action_type", "")
                    entry = data[student_id]
                    if action == "ac_nap":
                        entry["today_naps"].append(activity)
                        if entry["last_nap"] is None:
                            entry["last_nap"] = activity
                    elif action == "ac_potty":
                        entry["today_diapers"].append(activity)
                        if entry["last_diaper"] is None:
                            entry["last_diaper"] = activity
                    elif action == "ac_food":
                        if _is_bottle(activity):
                            entry["today_bottles"].append(activity)
                            if entry["last_bottle"] is None:
                                entry["last_bottle"] = activity
                        else:
                            entry["today_meals"].append(activity)
                            if entry["last_meal"] is None:
                                entry["last_meal"] = activity
                    elif action == "ac_checkin" and entry["last_checkin"] is None:
                        entry["last_checkin"] = activity
                    elif action in ("ac_photo", "ac_video"):
                        entry["today_photos"].append(activity)
                        if entry["last_photo"] is None:
                            entry["last_photo"] = activity
                    elif action in ("ac_note", "ac_observation", "ac_kudo"):
                        entry["today_messages"].append(activity)
                        if entry["last_message"] is None:
                            entry["last_message"] = activity

            return data

        except Exception as err:
            raise UpdateFailed(
                f"Error communicating with Brightwheel: {err}"
            ) from err
