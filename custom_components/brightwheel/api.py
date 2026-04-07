"""Async API client for Brightwheel."""

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://schools.mybrightwheel.com/api/v1"
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "X-Client-Version": "106",
    "X-Client-Name": "web",
}


class BrightwheelAuthError(Exception):
    """Raised when authentication fails."""


class BrightwheelClient:
    """Async client for the Brightwheel API.

    Uses the shared HA aiohttp session but manages the Brightwheel auth
    cookie manually via a header so as not to pollute the shared cookie jar.

    Supports two auth modes:
    1. Direct auth cookie (recommended) — bypasses PerimeterX bot protection
    2. Email/password login (may be blocked by bot protection)
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str = "",
        password: str = "",
        auth_cookie: str | None = None,
    ) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._auth_cookie: str | None = auth_cookie
        self._user_id: str | None = None

    @property
    def _headers(self) -> dict[str, str]:
        """Return request headers including the auth cookie when available."""
        headers = {**DEFAULT_HEADERS}
        if self._auth_cookie:
            headers["Cookie"] = f"_brightwheel_v2={self._auth_cookie}"
        return headers

    async def authenticate(self) -> bool:
        """Authenticate with Brightwheel.

        If an auth cookie was provided, validates it by calling /users/me.
        Otherwise, attempts email/password login (may fail due to bot protection).
        """
        if self._auth_cookie:
            # Validate the pre-supplied cookie
            try:
                user = await self.get_user()
                self._user_id = user.get("object_id")
                _LOGGER.debug("Brightwheel cookie auth successful for user %s", self._user_id)
                return True
            except Exception:
                _LOGGER.error("Brightwheel cookie validation failed")
                self._auth_cookie = None
                return False

        # Fallback: email/password login (may be blocked by PerimeterX)
        payload = {"user": {"email": self._email, "password": self._password}}
        try:
            async with self._session.post(
                f"{BASE_URL}/sessions",
                json=payload,
                headers=DEFAULT_HEADERS,
            ) as resp:
                if resp.status != 200:
                    _LOGGER.error(
                        "Brightwheel auth failed with status %s (bot protection may be active)",
                        resp.status,
                    )
                    return False

                for cookie in resp.cookies.values():
                    if cookie.key == "_brightwheel_v2":
                        self._auth_cookie = cookie.value
                        break

                if not self._auth_cookie:
                    raw = resp.headers.getall("Set-Cookie", [])
                    for header_val in raw:
                        if "_brightwheel_v2=" in header_val:
                            part = header_val.split("_brightwheel_v2=")[1]
                            self._auth_cookie = part.split(";")[0]
                            break

                if not self._auth_cookie:
                    _LOGGER.error("Auth cookie not found in response")
                    return False

                _LOGGER.debug("Brightwheel email/password auth successful")
                return True
        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error during authentication: %s", err)
            raise

    async def get_user(self) -> dict[str, Any]:
        """Get the current authenticated user."""
        async with self._session.get(
            f"{BASE_URL}/users/me", headers=self._headers
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_students(self) -> list[dict[str, Any]]:
        """Get list of students for the authenticated guardian."""
        if self._user_id is None:
            user = await self.get_user()
            self._user_id = user["object_id"]
            _LOGGER.debug("Brightwheel user_id: %s", self._user_id)

        async with self._session.get(
            f"{BASE_URL}/guardians/{self._user_id}/students",
            headers=self._headers,
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            students = data.get("students", [])
            _LOGGER.debug("Brightwheel found %d students", len(students))
            if not students:
                _LOGGER.warning("Brightwheel: no students found for this account")
            return students

    async def get_activities(
        self,
        student_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get activities for a student, optionally filtered by date range."""
        params: dict[str, str | int] = {"page": 0, "page_size": 50}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        async with self._session.get(
            f"{BASE_URL}/students/{student_id}/activities",
            headers=self._headers,
            params=params,
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get("activities", [])

    async def close(self) -> None:
        """Clean up (no-op since we use the shared HA session)."""
        self._auth_cookie = None
        self._user_id = None
