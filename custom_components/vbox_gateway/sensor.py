"""Sensors based on captured firmware VJ.2.66.20 XML and HTML."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from . import VBoxCoordinator
from .api import _number
from .entity import VBoxEntity


def stream_at(data: dict, index: int) -> dict:
    details = data["stream_status"].get("streams", [])
    if len(details) > index:
        return details[index]
    active = data["active"]["streams"]
    return active[index] if len(active) > index else {}


def active_channel_names(data: dict) -> str | None:
    """List every unique currently streamed channel in device order."""
    streams = data["stream_status"].get("streams") or data["active"]["streams"]
    names = dict.fromkeys(
        name for stream in streams
        if (name := stream.get("channel") or stream.get("name"))
    )
    return ", ".join(names) if names else None


SPECS: tuple[tuple[str, str, Callable, str | None, bool], ...] = (
    ("last_success", "Poslední úspěšné načtení", lambda c, d: c.last_success, None, True),
    ("active_count", "Aktivní streamy", lambda c, d: d["active"]["count"], None, False),
    ("recordings", "Běžící nahrávání", lambda c, d: d["stream_status"].get("recordings"), None, False),
    ("cpu", "Zatížení CPU", lambda c, d: d["system"].get("cpu"), "%", False),
    ("memory", "Využití paměti", lambda c, d: d["system"].get("memory"), "%", False),
    ("temperature", "Teplota CPU", lambda c, d: d["system"].get("temperature"), "°C", False),
    ("uptime", "Doba běhu", lambda c, d: d["system"].get("uptime"), None, True),
    ("stream_bitrate", "Celkový datový tok", lambda c, d: d["active"]["bitrate"], "Mbit/s", False),
    ("stream_channel", "Aktivní kanály", lambda c, d: active_channel_names(d), None, False),
    ("stream_tuner", "Stream 1 tuner", lambda c, d: stream_at(d, 0).get("tuner"), None, False),
    ("stream_audio", "Stream 1 jazyk zvuku", lambda c, d: stream_at(d, 0).get("audio"), None, False),
    ("stream_subtitles", "Stream 1 jazyk titulků", lambda c, d: stream_at(d, 0).get("subtitles"), None, False),
    ("stream_destination", "Stream 1 cíl", lambda c, d: stream_at(d, 0).get("destination"), None, True),
    ("stream_1_bitrate", "Stream 1 datový tok", lambda c, d: stream_at(d, 0).get("bitrate"), "Mbit/s", False),
    ("stream_2_channel", "Stream 2 kanál", lambda c, d: stream_at(d, 1).get("channel") or stream_at(d, 1).get("name"), None, False),
    ("stream_2_tuner", "Stream 2 tuner", lambda c, d: stream_at(d, 1).get("tuner"), None, False),
    ("stream_2_audio", "Stream 2 jazyk zvuku", lambda c, d: stream_at(d, 1).get("audio"), None, False),
    ("stream_2_subtitles", "Stream 2 jazyk titulků", lambda c, d: stream_at(d, 1).get("subtitles"), None, False),
    ("stream_2_destination", "Stream 2 cíl", lambda c, d: stream_at(d, 1).get("destination"), None, True),
    ("stream_2_bitrate", "Stream 2 datový tok", lambda c, d: stream_at(d, 1).get("bitrate"), "Mbit/s", False),
    ("channels_total", "Naladěné stanice", lambda c, d: (d["channels"] or {}).get("total"), None, False),
    ("channels_tv", "TV stanice", lambda c, d: (d["channels"] or {}).get("tv"), None, False),
    ("channels_radio", "Rádia", lambda c, d: (d["channels"] or {}).get("radio"), None, False),
    ("device_name", "Název zařízení", lambda c, d: d["board"].get("DeviceName"), None, True),
    ("model", "Model", lambda c, d: d["board"].get("ProductName"), None, True),
    ("product_number", "Produktové číslo", lambda c, d: d["board"].get("ProductNumber"), None, True),
    ("software", "Verze softwaru", lambda c, d: d["board"].get("SoftwareVersion"), None, True),
    ("hardware", "Revize hardwaru", lambda c, d: d["board"].get("HWRev"), None, True),
    ("firmware", "Verze firmwaru", lambda c, d: d["board"].get("FWRev"), None, True),
    ("kernel", "Verze kernelu", lambda c, d: d["board"].get("KernelVersion"), None, True),
    ("bootloader", "Verze bootloaderu", lambda c, d: d["board"].get("UbootVersion"), None, True),
    ("tuner_count", "Počet tunerů", lambda c, d: _number(d["board"].get("TunersNumber")), None, True),
    ("serial", "Sériové číslo", lambda c, d: d["board"].get("SerialNum"), None, True),
)

TUNER_FIELDS = (
    ("LockStatus", "Stav", None, False),
    ("TunerType", "Typ", None, True),
    ("SignalStrength", "Síla signálu", "%", False),
    ("RFLevel", "RF úroveň", "dBm", False),
    ("SNR", "SNR", "dB", False),
    ("BER", "BER", "BER", True),
    ("ChannelNumber", "Kanál", "kanál", False),
    ("Frequency", "Frekvence", "kHz", False),
    ("Bandwidth", "Šířka pásma", "MHz", True),
    ("DvbMode", "DVB režim", None, True),
    ("PlpId", "PLP ID", "ID", True),
    ("Modulation", "Modulace", None, True),
    ("GuardInterval", "Guard interval", None, True),
    ("CodeRate", "Code rate", None, True),
)

SERVICE_NAMES = (
    "VBOX_DAEMON", "VERSACAST", "SNMP", "STREAMER",
    "UPNP_SERVER", "SYSLOG_DAEMON", "VBOX_WATCHDOG",
)


class VBoxSensor(VBoxEntity, SensorEntity):
    def __init__(self, coordinator, key, name, getter, unit=None, diagnostic=False):
        super().__init__(coordinator, key)
        self._attr_translation_key = key
        self.getter = getter
        self._attr_native_unit_of_measurement = unit
        if key == "last_success":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        if diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self):
        if self.unique_id.endswith("_last_success"):
            return self.coordinator.last_success is not None
        return super().available

    @property
    def native_value(self):
        return self.getter(self.coordinator, self.coordinator.data)

    @property
    def extra_state_attributes(self):
        if self.unique_id.endswith("_active_count"):
            return {"streams": self.coordinator.data["active"]["streams"]}
        if self.unique_id.endswith("_stream_channel"):
            return {"streams": self.coordinator.data["stream_status"].get("streams", [])}
        return None


def service_errors(coordinator, data):
    states = data["services"]
    if not states:
        return None
    return sum(value not in ("STARTED", "DISABLED", "STOPPED") for value in states.values())


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    c = entry.runtime_data
    entities = [VBoxSensor(c, key, name, getter, unit, diagnostic) for key, name, getter, unit, diagnostic in SPECS]
    for tuner in ("1", "2"):
        for field, label, unit, diagnostic in TUNER_FIELDS:
            entities.append(VBoxSensor(
                c, f"tuner_{tuner}_{field}", f"Tuner {tuner} {label}",
                lambda coord, data, t=tuner, f=field, u=unit: (
                    _number(data["tuners"][t].get(f)) if u else data["tuners"][t].get(f) or None
                ),
                None if unit in ("BER", "kanál", "ID") else unit, diagnostic,
            ))
    for service in SERVICE_NAMES:
        entities.append(VBoxSensor(
            c, f"service_{service}", f"Služba {service}",
            lambda coord, data, s=service: data["services"].get(s),
            diagnostic=True,
        ))
    entities.append(VBoxSensor(c, "service_errors", "Služby v chybě", service_errors, diagnostic=True))
    async_add_entities(entities)
