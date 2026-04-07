"""Config flow for Brightwheel integration."""

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BrightwheelClient
from .const import CONF_AUTH_COOKIE, CONF_EMAIL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class BrightwheelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Brightwheel.

    Brightwheel uses PerimeterX bot protection, so direct email/password
    login from a server is blocked. Instead, the user provides their
    _brightwheel_v2 auth cookie extracted from a browser session.

    Use the refresh_brightwheel_cookie.js helper script to obtain the cookie.
    """

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step — ask for auth cookie."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = BrightwheelClient(
                session, auth_cookie=user_input[CONF_AUTH_COOKIE]
            )
            try:
                if await client.authenticate():
                    user = await client.get_user()
                    email = user.get("email", "unknown")
                    await self.async_set_unique_id(email)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Brightwheel ({email})",
                        data={
                            CONF_AUTH_COOKIE: user_input[CONF_AUTH_COOKIE],
                            CONF_EMAIL: email,
                        },
                    )
                else:
                    errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during Brightwheel config")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AUTH_COOKIE): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "cookie_help": "Run the refresh_brightwheel_cookie.js script to obtain your auth cookie."
            },
        )

    async def async_step_reconfigure(self, user_input=None):
        """Handle reconfiguration — update the auth cookie."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = BrightwheelClient(
                session, auth_cookie=user_input[CONF_AUTH_COOKIE]
            )
            try:
                if await client.authenticate():
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data_updates={
                            CONF_AUTH_COOKIE: user_input[CONF_AUTH_COOKIE],
                        },
                    )
                else:
                    errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during Brightwheel reconfigure")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AUTH_COOKIE): str,
                }
            ),
            errors=errors,
        )
