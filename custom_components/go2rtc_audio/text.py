"""Champs de saisie par caméra — URL radio personnalisée et message TTS."""

from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_CAMERAS, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    added: set[str] = set()

    @callback
    def _sync_entities(*_args) -> None:
        cameras = entry.options.get(CONF_CAMERAS, [])
        new_entities = []
        for cam in cameras:
            name = cam["name"]
            if name in added:
                continue
            new_entities.append(RadioUrlText(entry, name))
            new_entities.append(MessageText(entry, name))
            added.add(name)
        if new_entities:
            async_add_entities(new_entities)

    _sync_entities()

    async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
        _sync_entities()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))


class _BaseCameraText(TextEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_native_min = 0
    _attr_native_max = 255

    def __init__(self, entry: ConfigEntry, camera: str, key: str) -> None:
        self._attr_unique_id = f"{entry.entry_id}_{camera}_{key}"
        self._attr_translation_key = key
        self._attr_native_value = ""
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, camera)},
            name=camera,
            manufacturer="go2rtc Audio Diffusion",
            model="Caméra audio bidirectionnel",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_native_value = last_state.state

    async def async_set_value(self, value: str) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()


class RadioUrlText(_BaseCameraText):
    """URL du flux radio personnalisée à diffuser."""

    _attr_icon = "mdi:radio"

    def __init__(self, entry: ConfigEntry, camera: str) -> None:
        super().__init__(entry, camera, "radio_url")


class MessageText(_BaseCameraText):
    """Message à convertir en TTS et diffuser."""

    _attr_icon = "mdi:message-text"
    _attr_mode = "text"
    _attr_native_max = 500

    def __init__(self, entry: ConfigEntry, camera: str) -> None:
        super().__init__(entry, camera, "message")
