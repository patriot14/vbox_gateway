"""Gateway and tuner status."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .entity import VBoxEntity


class VBoxOnline(VBoxEntity, BinarySensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator, "online")
        self._attr_name = "Dostupnost"

    @property
    def available(self):
        return True

    @property
    def is_on(self):
        return self.coordinator.last_update_success


class VBoxTunerSignal(VBoxEntity, BinarySensorEntity):
    def __init__(self, coordinator, tuner):
        super().__init__(coordinator, f"tuner_{tuner}_signal")
        self.tuner = tuner
        self._attr_name = f"Tuner {tuner} má signál"

    @property
    def is_on(self):
        return self.coordinator.data["tuners"][self.tuner].get("LockStatus") == "LOCKED"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    c = entry.runtime_data
    async_add_entities([VBoxOnline(c), VBoxTunerSignal(c, "1"), VBoxTunerSignal(c, "2")])
