"""Config flow with optional HTTP Basic authentication for ManageApp pages."""

from __future__ import annotations

import ipaddress

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import VBoxAuthError, VBoxClient, VBoxError
from .const import CONF_USE_AUTH, DEFAULT_HOST, DOMAIN


class VBoxFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._host = DEFAULT_HOST

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                ipaddress.IPv4Address(host)
            except ValueError:
                errors[CONF_HOST] = "invalid_host"
            else:
                self._host = host
                if user_input[CONF_USE_AUTH]:
                    return await self.async_step_credentials()
                return await self._finish({CONF_HOST: host, CONF_USE_AUTH: False})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=self._host): str,
                vol.Required(CONF_USE_AUTH, default=False): bool,
            }),
            errors=errors,
        )

    async def async_step_credentials(self, user_input=None):
        errors = {}
        if user_input is not None:
            return await self._finish({
                CONF_HOST: self._host, CONF_USE_AUTH: True,
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            })
        return self.async_show_form(
            step_id="credentials",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    async def _finish(self, data):
        client = VBoxClient(
            async_get_clientsession(self.hass), data[CONF_HOST],
            data.get(CONF_USERNAME), data.get(CONF_PASSWORD),
        )
        try:
            board = await client.query("QueryBoardInfo")
            if data[CONF_USE_AUTH]:
                await client.page(0)
        except VBoxAuthError:
            error = "invalid_auth"
        except VBoxError:
            error = "cannot_connect"
        else:
            serial = board.findtext("SerialNum") or data[CONF_HOST]
            await self.async_set_unique_id(serial)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=board.findtext("DeviceName") or "VBox TV Gateway", data=data,
            )
        step = "credentials" if data[CONF_USE_AUTH] else "user"
        schema = (
            vol.Schema({vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str})
            if step == "credentials" else
            vol.Schema({
                vol.Required(CONF_HOST, default=self._host): str,
                vol.Required(CONF_USE_AUTH, default=False): bool,
            })
        )
        return self.async_show_form(step_id=step, data_schema=schema, errors={"base": error})
