"""VBox TV Gateway: coordinated local polling."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import VBoxAuthError, VBoxClient, VBoxError, _leaves, parse_active, parse_services, parse_streams, parse_system
from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ("sensor", "binary_sensor", "button")


class VBoxCoordinator(DataUpdateCoordinator[dict]):
    """Fast state with independently retried optional pages and channel counts."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=30),
            config_entry=entry,
        )
        self.entry = entry
        self.client = VBoxClient(
            async_get_clientsession(hass), entry.data[CONF_HOST],
            entry.data.get(CONF_USERNAME), entry.data.get(CONF_PASSWORD),
        )
        self.board: dict = {}
        self.channels: dict | None = None
        self.channel_refresh: datetime | None = None
        self.last_success: datetime | None = None
        self.web_error: str | None = None

    async def _async_update_data(self) -> dict:
        try:
            board, tuner1, tuner2, active = await asyncio.gather(
                self.client.query("QueryBoardInfo"),
                self.client.query("QueryLockStatus", TunerID="1"),
                self.client.query("QueryLockStatus", TunerID="2"),
                self.client.query("QueryActiveChannels"),
            )
        except VBoxError as exc:
            raise UpdateFailed(str(exc)) from exc
        self.board = _leaves(board)
        result = {
            "board": self.board,
            "tuners": {"1": _leaves(tuner1), "2": _leaves(tuner2)},
            "active": parse_active(active),
            "system": {}, "services": {}, "stream_status": {},
            "channels": self.channels,
        }
        now = dt_util.utcnow()
        if self.channel_refresh is None or now - self.channel_refresh > timedelta(hours=1):
            try:
                self.channels = await self.client.channels()
                self.channel_refresh = now
            except VBoxError as exc:
                _LOGGER.debug("Channel counts unavailable: %s", exc)
        result["channels"] = self.channels

        errors = []
        for key, option, parser in (
            ("system", 0, parse_system),
            ("services", 2, parse_services),
            ("stream_status", 30, parse_streams),
        ):
            try:
                result[key] = parser(await self.client.page(option))
            except (VBoxError, ValueError) as exc:
                errors.append(f"{key}: {exc}")
        self.web_error = "; ".join(errors) if errors else None
        if errors:
            _LOGGER.debug("Optional status pages unavailable: %s", self.web_error)
        self.last_success = now
        return result


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = VBoxCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
