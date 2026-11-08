"""go2rtc Audio Diffusion — diffuse du son (TTS, fichier, radio live) sur des
caméras à audio bidirectionnel, via une instance go2rtc dédiée (indépendante
de Frigate et du go2rtc natif de Home Assistant)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import voluptuous as vol
from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.components.media_source import async_resolve_media
from homeassistant.components.tts.media_source import generate_media_source_id
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

PLATFORMS = [Platform.BUTTON, Platform.TEXT, Platform.SELECT, Platform.BINARY_SENSOR]

from .const import (
    ATTR_CAMERA,
    ATTR_MEDIA_FILE,
    ATTR_MESSAGE,
    ATTR_MOTEUR_TTS,
    ATTR_RADIO_URL,
    ATTR_UPLOAD_FILE,
    ATTR_VOICE,
    CONF_API_PORT,
    CONF_CAMERAS,
    DEFAULT_API_PORT,
    DEFAULT_TTS_ENGINE,
    DOMAIN,
    SERVICE_DIFFUSER,
)
from .go2rtc_manager import Go2rtcManager, async_materialize_local
from .tts_helpers import tts_options_for_voice

_LOGGER = logging.getLogger(__name__)

DIFFUSER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CAMERA): cv.string,
        vol.Optional(ATTR_RADIO_URL): cv.string,
        vol.Optional(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_MOTEUR_TTS, default=DEFAULT_TTS_ENGINE): cv.entity_id,
        vol.Optional(ATTR_VOICE): cv.string,
        vol.Optional(ATTR_MEDIA_FILE): vol.Any(dict, cv.string),
        vol.Optional(ATTR_UPLOAD_FILE): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api_port = entry.options.get(CONF_API_PORT, DEFAULT_API_PORT)
    manager = Go2rtcManager(hass, api_port)
    await manager.async_start()
    await manager.async_sync_cameras(entry.options.get(CONF_CAMERAS, []))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _stop(_event) -> None:
        await manager.async_stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop)
    )
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    async def diffuser(call: ServiceCall) -> None:
        camera = call.data[ATTR_CAMERA]
        radio_url = call.data.get(ATTR_RADIO_URL)
        message = call.data.get(ATTR_MESSAGE)
        media_file = call.data.get(ATTR_MEDIA_FILE)
        upload_file = call.data.get(ATTR_UPLOAD_FILE)

        if radio_url:
            await manager.async_play(camera, "live", radio_url)
            return

        if upload_file:
            def _copy_upload() -> str:
                with process_uploaded_file(hass, upload_file) as src_path:
                    dest_dir = Path(hass.config.path("go2rtc_audio", "uploads"))
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    dest_path = dest_dir / src_path.name
                    shutil.copy(src_path, dest_path)
                    return str(dest_path)

            file_path = await hass.async_add_executor_job(_copy_upload)
            await manager.async_play(camera, "file", file_path)
            return

        if media_file:
            media_content_id = (
                media_file.get("media_content_id")
                if isinstance(media_file, dict)
                else media_file
            )
            play_item = await async_resolve_media(hass, media_content_id)
            value = await async_materialize_local(hass, play_item)
            await manager.async_play(camera, "file", value)
            return

        if message:
            engine = call.data[ATTR_MOTEUR_TTS]
            options = tts_options_for_voice(call.data.get(ATTR_VOICE))
            media_id = generate_media_source_id(
                hass, message=message, engine=engine, options=options, cache=True
            )
            play_item = await async_resolve_media(hass, media_id)
            value = await async_materialize_local(hass, play_item)
            await manager.async_play(camera, "file", value)
            return

        raise ServiceValidationError(
            "Remplis au moins un champ : flux radio, message, fichier du serveur "
            "ou fichier téléversé."
        )

    hass.services.async_register(
        DOMAIN, SERVICE_DIFFUSER, diffuser, schema=DIFFUSER_SCHEMA
    )

    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    manager: Go2rtcManager = hass.data[DOMAIN][entry.entry_id]
    await manager.async_sync_cameras(entry.options.get(CONF_CAMERAS, []))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    manager: Go2rtcManager = hass.data[DOMAIN].pop(entry.entry_id)
    await manager.async_stop()
    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, SERVICE_DIFFUSER)
    return unload_ok
