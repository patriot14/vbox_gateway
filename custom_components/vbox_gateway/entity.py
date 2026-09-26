"""Common VBox device identity."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VBoxCoordinator
from .const import DOMAIN


class VBoxEntity(CoordinatorEntity[VBoxCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: VBoxCoordinator, key: str) -> None:
        super().__init__(coordinator)
        serial = coordinator.board.get("SerialNum") or coordinator.client.host
        self._attr_unique_id = f"{serial}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer="VBox Communications",
            name=coordinator.board.get("DeviceName") or "VBox TV Gateway",
            model=coordinator.board.get("ProductName") or "XTi",
            sw_version=coordinator.board.get("SoftwareVersion"),
            hw_version=coordinator.board.get("HWRev"),
            serial_number=coordinator.board.get("SerialNum"),
            configuration_url=f"http://{coordinator.client.host}/",
        )
