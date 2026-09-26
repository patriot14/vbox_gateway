"""Read only VBox endpoints and the confirmed restart command."""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from html import unescape
import re
import xml.etree.ElementTree as ET

from aiohttp import BasicAuth, ClientError, ClientSession

from .const import API_PATH, MANAGE_PATH


class VBoxError(Exception):
    """VBox network or response error."""


class VBoxAuthError(VBoxError):
    """Protected web page rejected supplied credentials."""


def _number(text: str | None) -> float | None:
    """Parse units and scientific notation without changing unknown into zero."""
    if not text:
        return None
    match = re.search(r"[-+]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:e[-+]?\d+)?", text, re.I)
    return float(match.group().replace(",", ".")) if match else None


def _leaves(element: ET.Element) -> dict[str, str]:
    return {
        child.tag: (child.text or "").strip()
        for child in element.iter()
        if len(child) == 0
    }


def _input(html: str, name: str) -> str | None:
    tag = re.search(
        rf"<input\b(?=[^>]*\bname\s*=\s*[\"']?{re.escape(name)}\b)[^>]*>",
        html, re.I | re.S,
    )
    if tag is None:
        return None
    value = re.search(r"\bvalue\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]*))", tag.group(), re.I | re.S)
    return unescape(next((x for x in value.groups() if x is not None), "")).strip() if value else None


def parse_system(html: str) -> dict:
    """Read resources from the actual System Status page (OPTION=0)."""
    uptime = re.search(r"System Uptime.*?<input\b[^>]*\bvalue\s*=\s*[\"']([^\"']*)", html, re.I | re.S)
    return {
        "cpu": _number(_input(html, "CPU")),
        "memory": _number(_input(html, "Memory")),
        "temperature": _number(_input(html, "Temperature")),
        "uptime": unescape(uptime.group(1)).strip() if uptime else None,
    }


def parse_services(html: str) -> dict[str, str]:
    """Read the seven service rows without interpreting DISABLED as a fault."""
    names = (
        "VBOX_DAEMON", "VERSACAST", "SNMP", "STREAMER",
        "UPNP_SERVER", "SYSLOG_DAEMON", "VBOX_WATCHDOG",
    )
    result = {}
    for name in names:
        match = re.search(
            rf"<td[^>]*>\s*&nbsp;\s*{name}\s*</td>\s*<td[^>]*>(.*?)</td>",
            html, re.I | re.S,
        )
        if match:
            state = re.sub(r"<[^>]+>", " ", match.group(1))
            result[name] = unescape(state).replace("\xa0", " ").strip().upper()
    return result


def parse_streams(html: str) -> dict:
    """Read optional details available only on Streaming Status (OPTION=30)."""
    head, _, tail = html.partition("Running Recordings Status")
    streams = []
    for match in re.finditer(
        r"<a\b[^>]*\bname\s*=\s*[\"']?\d+[^>]*>(.*?)</a>\s*</td>(.*?)(?=<a\b[^>]*\bname\s*=\s*[\"']?\d+|</table>\s*<br>\s*The Bit rate)",
        head, re.I | re.S,
    ):
        raw = match.group(2)
        name = re.sub(r"<[^>]+>", "", match.group(1))
        tuner = re.search(r"\bTuner\s+(\d+)\b", raw, re.I)
        audio = re.search(r"Audio:\s*(?:&nbsp;|\s)*([^<]+)", raw, re.I)
        subtitle = re.search(r"Subtitles:\s*([^<]+)", raw, re.I)
        destination = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}:[\w-]+", raw)
        bitrate = re.search(r"</table>\s*</td>\s*<td[^>]*>\s*([\d.]+)", raw, re.I)
        streams.append({
            "channel": unescape(name).strip(),
            "tuner": int(tuner.group(1)) if tuner else None,
            "audio": unescape(audio.group(1)).replace("\xa0", " ").strip() if audio else None,
            "subtitles": unescape(subtitle.group(1)).strip() if subtitle else None,
            "destination": destination.group() if destination else None,
            "bitrate": _number(bitrate.group(1)) if bitrate else None,
        })
    if "No Recordings Info" in tail:
        recordings = 0
    else:
        # Only expose a count when the source clearly contains recording rows.
        section = tail.split("</TABLE>", 1)[1] if "</TABLE>" in tail else ""
        recordings = max(0, len(re.findall(r"<tr\b", section, re.I)) - 1) if section else None
    return {"streams": streams, "recordings": recordings}


def parse_channels(xml: str) -> dict[str, int]:
    """The XMLTV display-name at index 1 carries TV / Radio."""
    root = ET.fromstring(xml)
    if root.tag != "tv":
        raise VBoxError("Unexpected XMLTV root")
    channels = root.findall("channel")
    types = Counter(
        names[1].text.strip()
        for channel in channels
        if len(names := channel.findall("display-name")) > 1 and names[1].text
    )
    return {"total": len(channels), "tv": types["TV"], "radio": types["Radio"]}


def parse_active(reply: ET.Element) -> dict:
    result = []
    for channel in reply.findall("./Channels/Channel"):
        data = _leaves(channel)
        # The API numbers tuners from zero; the web UI and HA labels start at one.
        tuner_id = data.get("OnTunerId")
        try:
            tuner = int(tuner_id) + 1 if tuner_id is not None else None
        except ValueError:
            tuner = None
        result.append({
            "name": data.get("Name"),
            "tuner": tuner,
            "bitrate": _number(data.get("Bitrate")),
            "encrypted": data.get("Encrypted"),
        })
    return {
        "count": int(reply.findtext("NumOfChannels") or 0),
        "streams": result,
        "bitrate": sum(x["bitrate"] or 0 for x in result),
    }


class VBoxClient:
    def __init__(
        self, session: ClientSession, host: str, username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.session = session
        self.host = host
        self.auth = BasicAuth(username, password or "") if username else None

    async def _get(self, path: str, params: dict, protected: bool = False) -> str:
        try:
            async with asyncio.timeout(12):
                async with self.session.get(
                    f"http://{self.host}{path}", params=params,
                    auth=self.auth if protected else None,
                ) as response:
                    if response.status == 401:
                        raise VBoxAuthError("Invalid or missing web credentials")
                    response.raise_for_status()
                    return await response.text(errors="replace")
        except (ClientError, TimeoutError) as exc:
            raise VBoxError(str(exc)) from exc

    async def query(self, method: str, **params: str) -> ET.Element:
        xml = await self._get(API_PATH, {"OPTION": "1", "Method": method, **params})
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as exc:
            raise VBoxError("Invalid API XML") from exc
        if root.tag != "VboxHttpControl":
            raise VBoxError("Unexpected API response")
        code = root.findtext("./Status/ErrorCode")
        if code != "0":
            raise VBoxError(root.findtext("./Status/ErrorDescription") or f"API error: {code}")
        reply = root.find("Reply")
        if reply is None:
            raise VBoxError("Missing API Reply")
        return reply

    async def page(self, option: int) -> str:
        return await self._get(MANAGE_PATH, {"OPTION": str(option)}, protected=True)

    async def channels(self) -> dict[str, int]:
        xml = await self._get(API_PATH, {
            "OPTION": "1", "Method": "GetXmltvChannelsList",
            "FromChIndex": "FirstChannel", "ToChIndex": "LastChannel",
            "FilterBy": "All",
        })
        try:
            return parse_channels(xml)
        except ET.ParseError as exc:
            raise VBoxError("Invalid XMLTV response") from exc

    async def restart(self) -> None:
        """Confirmed by the device web UI's own SystemRestart request."""
        xml = await self._get(API_PATH, {"OPTION": "1", "Method": "SystemRestart"})
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as exc:
            raise VBoxError("Invalid restart response") from exc
        if root.tag != "VboxHttpControl" or root.findtext("./Status/ErrorCode") != "0":
            raise VBoxError("Restart command was rejected")
