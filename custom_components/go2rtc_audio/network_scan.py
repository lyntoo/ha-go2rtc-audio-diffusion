"""Découverte de caméras sur le réseau local via ONVIF WS-Discovery (sonde
multicast standard, pas un scan de ports agressif) — indépendant de toute
intégration HA existante (Frigate, etc.)."""

from __future__ import annotations

import socket
import time
import uuid
import xml.etree.ElementTree as ET

from homeassistant.core import HomeAssistant

_WSD_ADDR = ("239.255.255.250", 3702)

_PROBE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
            xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
            xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
            xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
  <e:Header>
    <w:MessageID>uuid:{msg_id}</w:MessageID>
    <w:To e:mustUnderstand="true">urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
    <w:Action e:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>
  </e:Header>
  <e:Body>
    <d:Probe>
      <d:Types>dn:NetworkVideoTransmitter</d:Types>
    </d:Probe>
  </e:Body>
</e:Envelope>"""

_NS = {"d": "http://schemas.xmlsoap.org/ws/2005/04/discovery"}


def _parse_hint(data: bytes) -> str:
    """Extrait un indice (fabricant/modèle) des Scopes ONVIF, si présents."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return ""
    scopes_el = root.find(".//d:Scopes", _NS)
    if scopes_el is None or not scopes_el.text:
        return ""
    hints = []
    for scope in scopes_el.text.split():
        lowered = scope.lower()
        if "hardware" in lowered or "name" in lowered:
            hints.append(scope.rsplit("/", 1)[-1])
    return ", ".join(hints[:2])


def _scan_sync(timeout: float) -> list[dict]:
    message = _PROBE_TEMPLATE.format(msg_id=uuid.uuid4())
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    found: dict[str, dict] = {}
    try:
        sock.sendto(message.encode("utf-8"), _WSD_ADDR)
        end_time = time.monotonic() + timeout
        while True:
            remaining = end_time - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(remaining)
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                break
            host = addr[0]
            if host not in found:
                found[host] = {"host": host, "hint": _parse_hint(data)}
    except OSError:
        pass
    finally:
        sock.close()
    return list(found.values())


async def async_scan_onvif_devices(hass: HomeAssistant, timeout: float = 4.0) -> list[dict]:
    """Sonde ONVIF WS-Discovery sur le réseau local, retourne les appareils
    trouvés sous la forme [{"host": ip, "hint": "fabricant/modèle ou vide"}]."""
    return await hass.async_add_executor_job(_scan_sync, timeout)
