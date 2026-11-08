"""Détection de caméra existante dans HA (fabricant/modèle via le registre
d'appareils) et construction de la ou des sources go2rtc correspondantes.

Mécanismes vérifiés dans la documentation officielle de go2rtc
(github.com/AlexxIT/go2rtc), pas devinés :
- Reolink : rtsp://user:pass@host/Preview_01_sub#backchannel=1 — VALIDÉ à
  l'oreille sur reofront/reodb (voir PROGRESS.md du projet).
- Hikvision : une source vidéo RTSP + une source audio séparée
  isapi://user:pass@host:80/ (internal/isapi/README.md) — non testé par
  l'utilisateur sur son matériel.
- Dahua / interphones Amcrest (OEM Dahua) :
  rtsp://user:pass@host/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif
  (internal/rtsp/README.md) — non testé par l'utilisateur sur son matériel.

Le mot de passe n'est JAMAIS lu depuis une autre intégration — seul le
host/IP est récupéré (via les config_entries de l'appareil), le mot de
passe est toujours celui que l'utilisateur retape dans notre propre champ.
"""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import quote

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import CONFIDENCE_BEST_EFFORT, CONFIDENCE_CONFIRMED


def _build_reolink(host: str, user: str, password: str) -> list[str]:
    return [f"rtsp://{quote(user)}:{quote(password)}@{host}/Preview_01_sub#backchannel=1"]


def _build_hikvision(host: str, user: str, password: str) -> list[str]:
    u, p = quote(user), quote(password)
    return [
        f"rtsp://{u}:{p}@{host}/Streaming/Channels/101",
        f"isapi://{u}:{p}@{host}:80/",
    ]


def _build_dahua_onvif(host: str, user: str, password: str) -> list[str]:
    u, p = quote(user), quote(password)
    return [
        f"rtsp://{u}:{p}@{host}/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif"
    ]


# Clé de marque -> (libellé affiché, constructeur de source(s), confiance).
# Accessible publiquement pour le sélecteur manuel ET pour la détection
# automatique (même registre, une seule source de vérité).
BRAND_BUILDERS: dict[str, tuple[str, Callable[[str, str, str], list[str]], str]] = {
    "reolink": ("Reolink", _build_reolink, CONFIDENCE_CONFIRMED),
    "hikvision": ("Hikvision", _build_hikvision, CONFIDENCE_BEST_EFFORT),
    "dahua": ("Dahua", _build_dahua_onvif, CONFIDENCE_BEST_EFFORT),
    "amcrest": ("Amcrest", _build_dahua_onvif, CONFIDENCE_BEST_EFFORT),
}


def _get_device(hass: HomeAssistant, camera_entity_id: str):
    entity_entry = er.async_get(hass).async_get(camera_entity_id)
    if entity_entry is None or entity_entry.device_id is None:
        return None
    return dr.async_get(hass).async_get(entity_entry.device_id)


def detect_brand(hass: HomeAssistant, camera_entity_id: str) -> str | None:
    """Retourne la clé de marque (ex: 'reolink') si le fabricant/modèle de
    cette entité caméra correspond à une marque connue, sinon None.

    Ne fonctionne PAS si la caméra est exposée via un NVR (ex: Frigate) —
    le fabricant/modèle du registre d'appareils HA reflète alors le NVR,
    pas la caméra physique. Dans ce cas, le sélecteur manuel de marque
    (voir config_flow.py) prend le relais."""
    device = _get_device(hass, camera_entity_id)
    if device is None:
        return None
    haystack = f"{device.manufacturer or ''} {device.model or ''}".lower()
    for key in BRAND_BUILDERS:
        if key in haystack:
            return key
    return None


def find_camera_host(hass: HomeAssistant, camera_entity_id: str) -> str | None:
    """Cherche l'adresse (host/IP) de la caméra via les config_entries de
    son appareil. Ne lit QUE le champ host — jamais les identifiants."""
    device = _get_device(hass, camera_entity_id)
    if device is None:
        return None
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            continue
        host = entry.data.get("host") or entry.data.get("ip_address") or entry.data.get("ip")
        if host:
            return host
    return None
