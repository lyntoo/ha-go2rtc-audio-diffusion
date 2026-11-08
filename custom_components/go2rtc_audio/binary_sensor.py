"""Indique si une diffusion audio (live/message/fichier) est active en ce
moment sur la caméra — autrement invisible depuis l'intérieur de la maison."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_CAMERAS, DOMAIN

SCAN_INTERVAL = timedelta(seconds=3)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    manager = hass.data[DOMAIN][entry.entry_id]
    added: set[str] = set()

    @callback
    def _sync_entities(*_args) -> None:
        cameras = entry.options.get(CONF_CAMERAS, [])
        new_entities = [
            DiffusionActiveSensor(manager, entry, cam["name"])
            for cam in cameras
            if cam["name"] not in added
        ]
        for cam in cameras:
            added.add(cam["name"])
        if new_entities:
            async_add_entities(new_entities)

    _sync_entities()

    async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
        _sync_entities()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))


class DiffusionActiveSensor(BinarySensorEntity):
    """On = une diffusion est en cours sur cette caméra, Off = silence."""

    _attr_has_entity_name = True
    _attr_translation_key = "diffusion_active"
    _attr_icon = "mdi:volume-high"
    _attr_should_poll = True

    def __init__(self, manager, entry: ConfigEntry, camera: str) -> None:
        self._manager = manager
        self._camera = camera
        self._attr_unique_id = f"{entry.entry_id}_{camera}_diffusion_active"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, camera)},
            name=camera,
            manufacturer="go2rtc Audio Diffusion",
            model="Caméra audio bidirectionnel",
        )
        self._attr_is_on = False

    async def async_update(self) -> None:
        self._attr_is_on = await self._manager.async_is_playing(self._camera)
        self._attr_icon = "mdi:volume-high" if self._attr_is_on else "mdi:volume-off"
