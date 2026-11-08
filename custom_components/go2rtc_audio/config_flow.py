"""Config flow — go2rtc Audio Diffusion."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, selector

from .camera_detection import BRAND_BUILDERS, detect_brand, find_camera_host
from .network_scan import async_scan_onvif_devices
from .const import (
    ATTR_CAMERA_BRAND_CHOICE,
    ATTR_CAMERA_ENTITY,
    ATTR_CAMERA_HOST,
    ATTR_CAMERA_PASSWORD,
    ATTR_CAMERA_USERNAME,
    CONF_API_PORT,
    CONF_CAMERA_BACKCHANNEL,
    CONF_CAMERA_BRAND,
    CONF_CAMERA_CONFIDENCE,
    CONF_CAMERA_NAME,
    CONF_CAMERA_URL,
    CONF_CAMERAS,
    DEFAULT_API_PORT,
    DOMAIN,
)

USER_SCHEMA = vol.Schema(
    {vol.Optional(CONF_API_PORT, default=DEFAULT_API_PORT): cv.port}
)

CAMERA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CAMERA_NAME): cv.string,
        vol.Optional(ATTR_CAMERA_ENTITY): selector.selector(
            {"entity": {"domain": "camera"}}
        ),
        vol.Optional(ATTR_CAMERA_BRAND_CHOICE, default="auto"): selector.selector(
            {
                "select": {
                    "mode": "dropdown",
                    "options": [
                        {"value": "auto", "label": "Détection automatique"},
                        {"value": "reolink", "label": "Reolink"},
                        {"value": "hikvision", "label": "Hikvision (best-effort, non testé)"},
                        {"value": "dahua", "label": "Dahua (best-effort, non testé)"},
                        {"value": "amcrest", "label": "Amcrest (best-effort, non testé)"},
                    ],
                }
            }
        ),
        vol.Optional(ATTR_CAMERA_HOST): cv.string,
        vol.Optional(ATTR_CAMERA_USERNAME, default="admin"): cv.string,
        vol.Optional(ATTR_CAMERA_PASSWORD): selector.selector(
            {"text": {"type": "password"}}
        ),
        vol.Optional(CONF_CAMERA_URL): cv.string,
        vol.Optional(CONF_CAMERA_BACKCHANNEL, default=True): cv.boolean,
    }
)


class Go2rtcAudioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Une seule instance : le processus go2rtc dédié est partagé par toutes
    les caméras ajoutées ensuite via l'options flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="go2rtc Audio Diffusion",
                data={},
                options={CONF_API_PORT: user_input[CONF_API_PORT], CONF_CAMERAS: []},
            )

        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return Go2rtcAudioOptionsFlow()


class Go2rtcAudioOptionsFlow(OptionsFlow):
    """Ajouter/retirer des caméras (streams go2rtc + backchannel)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        cameras = self.config_entry.options.get(CONF_CAMERAS, [])

        def _label(cam: dict[str, Any]) -> str:
            brand = cam.get(CONF_CAMERA_BRAND)
            if not brand:
                return cam[CONF_CAMERA_NAME]
            suffix = " — non testé" if cam.get(CONF_CAMERA_CONFIDENCE) == "best_effort" else ""
            return f"{cam[CONF_CAMERA_NAME]} ({brand}{suffix})"

        names = ", ".join(_label(c) for c in cameras) or "(aucune)"
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_camera", "remove_camera"],
            description_placeholders={"cameras": names},
        )

    async def async_step_add_camera(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input[CONF_CAMERA_NAME]
            camera_entity = user_input.get(ATTR_CAMERA_ENTITY)
            manual_url = user_input.get(CONF_CAMERA_URL)
            brand_choice = user_input.get(ATTR_CAMERA_BRAND_CHOICE, "auto")
            cam: dict[str, Any] = {CONF_CAMERA_NAME: name}

            # Marque explicitement choisie dans la liste, OU détectée depuis
            # la caméra existante (si "auto"). La détection auto échoue pour
            # une caméra exposée via un NVR (ex: Frigate), qui masque le
            # vrai fabricant — le choix manuel sert justement ce cas-là.
            brand_key: str | None = (
                brand_choice if brand_choice != "auto"
                else (detect_brand(self.hass, camera_entity) if camera_entity else None)
            )

            if brand_key:
                label, builder, confidence = BRAND_BUILDERS[brand_key]
                password = user_input.get(ATTR_CAMERA_PASSWORD)
                host = user_input.get(ATTR_CAMERA_HOST) or (
                    find_camera_host(self.hass, camera_entity) if camera_entity else None
                )
                if not password:
                    errors[ATTR_CAMERA_PASSWORD] = "password_required"
                elif not host:
                    errors[ATTR_CAMERA_HOST] = "host_required"
                else:
                    username = user_input.get(ATTR_CAMERA_USERNAME, "admin")
                    cam[CONF_CAMERA_URL] = builder(host, username, password)
                    cam[CONF_CAMERA_BACKCHANNEL] = False
                    cam[CONF_CAMERA_BRAND] = label
                    cam[CONF_CAMERA_CONFIDENCE] = confidence
            elif manual_url:
                cam[CONF_CAMERA_URL] = manual_url
                cam[CONF_CAMERA_BACKCHANNEL] = user_input.get(CONF_CAMERA_BACKCHANNEL, True)
            elif camera_entity:
                errors["base"] = "brand_not_recognized"
            else:
                errors["base"] = "need_entity_or_url"

            if not errors:
                cameras = list(self.config_entry.options.get(CONF_CAMERAS, []))
                cameras = [c for c in cameras if c[CONF_CAMERA_NAME] != name]
                cameras.append(cam)
                return self.async_create_entry(
                    data={**self.config_entry.options, CONF_CAMERAS: cameras}
                )

        # Sonde ONVIF WS-Discovery sur le réseau local (indépendant de toute
        # intégration HA existante) — purement informatif, affiché dans la
        # description pour aider à trouver l'adresse à taper dans "host".
        devices = await async_scan_onvif_devices(self.hass)
        if devices:
            lines = "\n".join(
                f"- {d['host']}" + (f" ({d['hint']})" if d["hint"] else "")
                for d in devices
            )
            found_cameras = f"Caméras trouvées sur le réseau (ONVIF) :\n{lines}"
        else:
            found_cameras = (
                "Aucune caméra ONVIF trouvée automatiquement sur le réseau "
                "(normal si la caméra est derrière un NVR comme Frigate, ou "
                "ne répond pas à ONVIF/WS-Discovery)."
            )

        return self.async_show_form(
            step_id="add_camera",
            data_schema=CAMERA_SCHEMA,
            errors=errors,
            description_placeholders={"found_cameras": found_cameras},
        )

    async def async_step_remove_camera(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        cameras = list(self.config_entry.options.get(CONF_CAMERAS, []))
        names = [c[CONF_CAMERA_NAME] for c in cameras]

        if not names:
            return self.async_abort(reason="no_cameras")

        if user_input is not None:
            remaining = [
                c for c in cameras if c[CONF_CAMERA_NAME] not in user_input["names"]
            ]
            return self.async_create_entry(
                data={**self.config_entry.options, CONF_CAMERAS: remaining}
            )

        schema = vol.Schema(
            {vol.Required("names"): cv.multi_select({n: n for n in names})}
        )
        return self.async_show_form(step_id="remove_camera", data_schema=schema)
