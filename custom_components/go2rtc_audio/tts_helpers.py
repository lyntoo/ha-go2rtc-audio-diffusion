"""Utilitaires partagés : lecture d'entités sœurs (même caméra) et résolution
des voix TTS disponibles pour le moteur actuellement choisi.

Vérifié dans le code source HA Core (homeassistant/components/tts/) :
- `get_engine_instance(hass, engine)` (tts/helper.py) retourne l'entité TTS
  (ou le Provider legacy) pour un entity_id comme "tts.piper".
- `instance.supported_options` (liste de str | None) doit contenir "voice"
  pour que le moteur supporte le choix de voix.
- `instance.async_get_supported_voices(language)` retourne une liste de
  `Voice(voice_id, name)` ou None si le moteur ne la surcharge pas.
- La clé "voice" dans le dict `options` de `generate_media_source_id()` est
  celle attendue par `TextToSpeechCommonOption.VOICE` (tts/const.py).
"""

from __future__ import annotations

from homeassistant.components.tts.helper import get_engine_instance
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DEFAULT_VOICE_OPTION, DOMAIN


def sibling_state(hass: HomeAssistant, domain: str, entry_id: str, camera: str, key: str):
    """Trouve l'état d'une entité sœur (même caméra) par son unique_id."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(domain, DOMAIN, f"{entry_id}_{camera}_{key}")
    return hass.states.get(entity_id) if entity_id else None


def voice_options_for_engine(hass: HomeAssistant, engine_id: str) -> list[str]:
    """Liste des voice_id disponibles pour ce moteur TTS, ou [] si le moteur
    ne supporte pas le choix de voix (ex. Piper selon la config, ou un
    moteur qui ne surcharge pas async_get_supported_voices)."""
    instance = get_engine_instance(hass, engine_id)
    if instance is None:
        return []
    supported_options = instance.supported_options or []
    if "voice" not in supported_options:
        return []
    get_voices = getattr(instance, "async_get_supported_voices", None)
    if get_voices is None:
        return []
    try:
        language = instance.default_language
    except AttributeError:
        return []
    voices = get_voices(language) or []
    return [v.voice_id for v in voices]


def tts_options_for_voice(voice_choice: str | None) -> dict | None:
    """Construit le dict `options` pour generate_media_source_id à partir du
    choix de voix (None si pas de choix précis -> le moteur décide)."""
    if not voice_choice or voice_choice == DEFAULT_VOICE_OPTION:
        return None
    return {"voice": voice_choice}
