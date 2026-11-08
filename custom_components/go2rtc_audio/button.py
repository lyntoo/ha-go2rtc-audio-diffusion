"""Boutons par caméra : diffusent la valeur actuelle des champs texte (URL
radio / message TTS) de cette même caméra."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.components.media_source import async_resolve_media
from homeassistant.components.tts.media_source import generate_media_source_id
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_CAMERAS, DEFAULT_TTS_ENGINE, DOMAIN
from .go2rtc_manager import async_materialize_local
from .tts_helpers import sibling_state, tts_options_for_voice


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    manager = hass.data[DOMAIN][entry.entry_id]
    added: set[str] = set()

    @callback
    def _sync_entities(*_args) -> None:
        cameras = entry.options.get(CONF_CAMERAS, [])
        new_entities = []
        for cam in cameras:
            name = cam["name"]
            if name in added:
                continue
            new_entities.append(PlayRadioButton(hass, manager, entry, name))
            new_entities.append(PlayMessageButton(hass, manager, entry, name))
            new_entities.append(StopButton(hass, manager, entry, name))
            added.add(name)
        if new_entities:
            async_add_entities(new_entities)

    _sync_entities()

    async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
        _sync_entities()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))


class _BaseCameraButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, manager, entry: ConfigEntry, camera: str, key: str) -> None:
        self._hass = hass
        self._manager = manager
        self._entry = entry
        self._camera = camera
        self._attr_unique_id = f"{entry.entry_id}_{camera}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, camera)},
            name=camera,
            manufacturer="go2rtc Audio Diffusion",
            model="Caméra audio bidirectionnel",
        )


class PlayRadioButton(_BaseCameraButton):
    """Diffuse l'URL actuellement saisie dans le champ « URL radio »."""

    _attr_icon = "mdi:radio"

    def __init__(self, hass: HomeAssistant, manager, entry: ConfigEntry, camera: str) -> None:
        super().__init__(hass, manager, entry, camera, "play_radio")

    async def async_press(self) -> None:
        state = sibling_state(self._hass, "text", self._entry.entry_id, self._camera, "radio_url")
        url = state.state if state else ""
        if not url:
            raise HomeAssistantError("Le champ « URL radio » est vide.")
        await self._manager.async_play(self._camera, "live", url)


class PlayMessageButton(_BaseCameraButton):
    """Convertit en TTS (moteur choisi) et diffuse le champ « Message TTS »."""

    _attr_icon = "mdi:bullhorn"

    def __init__(self, hass: HomeAssistant, manager, entry: ConfigEntry, camera: str) -> None:
        super().__init__(hass, manager, entry, camera, "play_message")

    async def async_press(self) -> None:
        msg_state = sibling_state(self._hass, "text", self._entry.entry_id, self._camera, "message")
        engine_state = sibling_state(self._hass, "select", self._entry.entry_id, self._camera, "tts_engine")
        voice_state = sibling_state(self._hass, "select", self._entry.entry_id, self._camera, "tts_voice")
        message = msg_state.state if msg_state else ""
        if not message:
            raise HomeAssistantError("Le champ « Message TTS » est vide.")
        engine = engine_state.state if engine_state else DEFAULT_TTS_ENGINE
        options = tts_options_for_voice(voice_state.state if voice_state else None)

        media_id = generate_media_source_id(
            self._hass, message=message, engine=engine, options=options, cache=True
        )
        play_item = await async_resolve_media(self._hass, media_id)
        value = await async_materialize_local(self._hass, play_item)
        await self._manager.async_play(self._camera, "file", value)


class StopButton(_BaseCameraButton):
    """Arrête proprement la diffusion en cours (sans message audible)."""

    _attr_icon = "mdi:stop-circle"

    def __init__(self, hass: HomeAssistant, manager, entry: ConfigEntry, camera: str) -> None:
        super().__init__(hass, manager, entry, camera, "stop")

    async def async_press(self) -> None:
        await self._manager.async_stop_play(self._camera)
