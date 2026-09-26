"""Manually initiated restart, using the command captured from the web UI."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory

from .api import VBoxError
from .entity import VBoxEntity


class VBoxRestart(VBoxEntity, ButtonEntity):
    _attr_name = "Restartovat zařízení"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator):
        super().__init__(coordinator, "restart")

    async def async_press(self):
        try:
            await self.coordinator.client.restart()
        except VBoxError as exc:
            raise HomeAssistantError(f"VBox restart failed: {exc}") from exc


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    async_add_entities([VBoxRestart(entry.runtime_data)])
