"""Choix du moteur TTS par caméra (Piper, HA Cloud, ou tout autre moteur TTS
installé sur cette instance Home Assistant)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_added_domain,
    async_track_state_change_event,
)
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_CAMERAS, DEFAULT_TTS_ENGINE, DEFAULT_VOICE_OPTION, DOMAIN
from .tts_helpers import sibling_state, voice_options_for_engine


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
            new_entities.append(TtsEngineSelect(hass, entry, name))
            new_entities.append(TtsVoiceSelect(hass, entry, name))
            added.add(name)
        if new_entities:
            async_add_entities(new_entities)

    _sync_entities()

    async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
        _sync_entities()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))


class TtsEngineSelect(SelectEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "tts_engine"
    _attr_icon = "mdi:account-voice"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, camera: str) -> None:
        self._hass = hass
        self._attr_unique_id = f"{entry.entry_id}_{camera}_tts_engine"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, camera)},
            name=camera,
            manufacturer="go2rtc Audio Diffusion",
            model="Caméra audio bidirectionnel",
        )
        self._attr_options = self._current_tts_options()
        self._attr_current_option = (
            DEFAULT_TTS_ENGINE
            if DEFAULT_TTS_ENGINE in self._attr_options
            else self._attr_options[0]
        )

    def _current_tts_options(self) -> list[str]:
        options = [state.entity_id for state in self._hass.states.async_all("tts")]
        return options or [DEFAULT_TTS_ENGINE]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        self._restored_option = last_state.state if last_state else None
        if self._restored_option in self._attr_options:
            self._attr_current_option = self._restored_option

        if self._hass.is_running:
            self._async_refresh_options()
        else:
            self.async_on_remove(
                self._hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STARTED, self._async_refresh_options
                )
            )

        # Certains moteurs TTS (Piper via Wyoming, HA Cloud) finissent de se
        # connecter bien après l'événement "démarré" (attente réseau/add-on) —
        # l'écouteur ponctuel ci-dessus peut donc rater leur apparition. On
        # suit en continu toute nouvelle entité du domaine "tts" tant que
        # cette entité existe.
        self.async_on_remove(
            async_track_state_added_domain(self._hass, ["tts"], self._async_refresh_options)
        )

    @callback
    def _async_refresh_options(self, _event: Event | None = None) -> None:
        """Les moteurs TTS (ex. Piper) peuvent finir de charger après cette
        intégration — on rafraîchit la liste une fois HA complètement démarré,
        et à chaque nouvelle entité TTS détectée par la suite."""
        options = self._current_tts_options()
        if set(options) == set(self._attr_options):
            return
        self._attr_options = options
        if self._restored_option in options:
            self._attr_current_option = self._restored_option
        elif self._attr_current_option not in options:
            self._attr_current_option = (
                DEFAULT_TTS_ENGINE if DEFAULT_TTS_ENGINE in options else options[0]
            )
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()


class TtsVoiceSelect(SelectEntity, RestoreEntity):
    """Choix de la voix précise pour le moteur TTS actuellement sélectionné
    (vide/« par défaut » si ce moteur ne supporte pas le choix de voix)."""

    _attr_has_entity_name = True
    _attr_translation_key = "tts_voice"
    _attr_icon = "mdi:microphone-variant"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, camera: str) -> None:
        self._hass = hass
        self._entry = entry
        self._camera = camera
        self._attr_unique_id = f"{entry.entry_id}_{camera}_tts_voice"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, camera)},
            name=camera,
            manufacturer="go2rtc Audio Diffusion",
            model="Caméra audio bidirectionnel",
        )
        self._attr_options = [DEFAULT_VOICE_OPTION]
        self._attr_current_option = DEFAULT_VOICE_OPTION
        self._restored_option: str | None = None

    def _engine_entity_id(self) -> str | None:
        state = sibling_state(self._hass, "select", self._entry.entry_id, self._camera, "tts_engine")
        return state.entity_id if state else None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        self._restored_option = last_state.state if last_state else None

        if self._hass.is_running:
            self._async_refresh_options()
        else:
            self.async_on_remove(
                self._hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STARTED, self._async_refresh_options
                )
            )

        engine_entity_id = self._engine_entity_id()
        if engine_entity_id:
            self.async_on_remove(
                async_track_state_change_event(
                    self._hass, [engine_entity_id], self._async_refresh_options
                )
            )

    @callback
    def _async_refresh_options(self, _event: Event | None = None) -> None:
        """Les voix disponibles dépendent du moteur TTS choisi (entité sœur) —
        on recalcule à chaque changement de moteur, et une fois au démarrage
        complet de HA (le moteur peut finir de charger après cette entité)."""
        engine_state = sibling_state(self._hass, "select", self._entry.entry_id, self._camera, "tts_engine")
        engine_id = engine_state.state if engine_state else DEFAULT_TTS_ENGINE
        voices = voice_options_for_engine(self._hass, engine_id)
        options = [DEFAULT_VOICE_OPTION, *voices]

        if options == self._attr_options:
            return
        self._attr_options = options
        if self._restored_option in options:
            self._attr_current_option = self._restored_option
        elif self._attr_current_option not in options:
            self._attr_current_option = DEFAULT_VOICE_OPTION
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()
