"""Gestion du binaire et du processus go2rtc dédié à cette intégration.

Instance go2rtc totalement indépendante (pas Frigate, pas le go2rtc natif HA) :
binaire officiel AlexxIT/go2rtc téléchargé dans le dossier de config de
l'intégration, lancé avec sa propre config (port API dédié, RTSP/WebRTC
désactivés — seule l'API HTTP est nécessaire pour la diffusion audio).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import platform
import stat
from pathlib import Path
from urllib.parse import quote

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url

from .const import GO2RTC_ASSETS, GO2RTC_VERSION

_LOGGER = logging.getLogger(__name__)

RELEASE_BASE_URL = "https://github.com/AlexxIT/go2rtc/releases/download"

# Clip silencieux (~0.3s) utilisé pour "arrêter" proprement une diffusion en
# cours : Stream.Play() (go2rtc) stoppe toujours l'ancien flux avant de jouer
# le nouveau — jouer ce silence déclenche cet arrêt sans message audible.
SILENCE_FILE = Path(__file__).parent / "assets" / "silence.wav"


class Go2rtcUnavailable(Exception):
    """Levée quand le binaire ou le processus go2rtc n'est pas disponible."""


async def async_materialize_local(hass: HomeAssistant, play_item) -> str:
    """Retourne un chemin de fichier LOCAL jouable par go2rtc.

    go2rtc choisit son gabarit ffmpeg selon le schéma de la source (voir
    internal/ffmpeg/ffmpeg.go) : un chemin local reçoit "-re -i" (cadencé en
    temps réel), une URL http(s) reçoit "-fflags nobuffer -flags low_delay"
    (pensé pour un vrai flux live, SANS -re). Donner une URL pour un fichier
    TTS/média fini fait lire ffmpeg plus vite que le temps réel, ce qui
    tronque l'audio avant que le backchannel ait fini de le transmettre.
    On télécharge donc toute source qui n'a qu'une URL pour forcer le
    gabarit "file"."""
    if play_item.path:
        return str(play_item.path)

    url = play_item.url
    if url.startswith("/"):
        url = get_url(hass) + url

    cache_dir = Path(hass.config.path("go2rtc_audio", "tts_cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(url.encode()).hexdigest()
    suffix = Path(url.split("?", 1)[0]).suffix or ".mp3"
    dest = cache_dir / f"{digest}{suffix}"

    if not await hass.async_add_executor_job(os.path.isfile, dest):
        session = async_get_clientsession(hass)
        async with session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.read()
        await hass.async_add_executor_job(dest.write_bytes, data)

    return str(dest)


def _storage_dir(hass: HomeAssistant) -> Path:
    path = Path(hass.config.path("go2rtc_audio"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _binary_path(hass: HomeAssistant) -> Path:
    suffix = ".exe" if platform.system() == "Windows" else ""
    return _storage_dir(hass) / f"go2rtc-{GO2RTC_VERSION}{suffix}"


def _asset_name() -> str | None:
    return GO2RTC_ASSETS.get((platform.system(), platform.machine()))


def _config_path(hass: HomeAssistant) -> Path:
    return _storage_dir(hass) / "go2rtc_audio.yaml"


def _write_binary_sync(path: Path, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _write_config_sync(path: Path, api_port: int) -> None:
    content = (
        "# Généré par l'intégration go2rtc_audio — ne pas éditer à la main.\n"
        "api:\n"
        f'  listen: ":{api_port}"\n'
        "rtsp:\n"
        '  listen: ""\n'
        "webrtc:\n"
        '  listen: ""\n'
    )
    path.write_text(content, encoding="utf-8")


async def async_ensure_binary(hass: HomeAssistant) -> Path:
    """Vérifie/télécharge le binaire go2rtc officiel pour cette plateforme."""
    path = _binary_path(hass)

    if await hass.async_add_executor_job(os.path.isfile, path):
        return path

    asset = _asset_name()
    if not asset:
        raise Go2rtcUnavailable(
            f"Plateforme non supportée: {platform.system()} {platform.machine()}"
        )

    url = f"{RELEASE_BASE_URL}/v{GO2RTC_VERSION}/{asset}"
    _LOGGER.info("Téléchargement du binaire go2rtc officiel: %s", url)

    session = async_get_clientsession(hass)
    async with session.get(url) as resp:
        resp.raise_for_status()
        data = await resp.read()

    if asset.endswith(".zip"):
        import io
        import zipfile

        def _unzip(raw: bytes) -> bytes:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                return zf.read(zf.namelist()[0])

        data = await hass.async_add_executor_job(_unzip, data)

    await hass.async_add_executor_job(_write_binary_sync, path, data)
    _LOGGER.info("Binaire go2rtc installé: %s", path)
    return path


class Go2rtcManager:
    """Gère le cycle de vie du processus go2rtc dédié et son API HTTP."""

    def __init__(self, hass: HomeAssistant, api_port: int) -> None:
        self.hass = hass
        self.api_port = api_port
        self.base_url = f"http://127.0.0.1:{api_port}/"
        self._binary: Path | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._log_task: asyncio.Task | None = None

    @property
    def available(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def async_start(self) -> None:
        self._binary = await async_ensure_binary(self.hass)
        config_path = _config_path(self.hass)
        await self.hass.async_add_executor_job(
            _write_config_sync, config_path, self.api_port
        )

        _LOGGER.info("Démarrage go2rtc (port API %s)", self.api_port)
        self._process = await asyncio.create_subprocess_exec(
            str(self._binary),
            "-c",
            str(config_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        self._log_task = self.hass.loop.create_task(self._drain_logs())

        # Attente courte que l'API soit prête avant de poursuivre
        for _ in range(20):
            if await self._api_ready():
                return
            await asyncio.sleep(0.25)
        _LOGGER.warning("go2rtc démarré mais l'API ne répond pas encore après 5s")

    async def _drain_logs(self) -> None:
        assert self._process is not None
        assert self._process.stdout is not None
        async for line in self._process.stdout:
            _LOGGER.debug("[go2rtc] %s", line.decode(errors="replace").rstrip())

    async def _api_ready(self) -> bool:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(self.base_url + "api", timeout=2) as resp:
                return resp.status == 200
        except Exception:  # noqa: BLE001
            return False

    async def async_stop(self, *_args) -> None:
        if self._process is None:
            return
        self._process.terminate()
        try:
            await asyncio.wait_for(self._process.wait(), timeout=5)
        except asyncio.TimeoutError:
            self._process.kill()
        if self._log_task:
            self._log_task.cancel()
        self._process = None

    async def async_register_stream(self, name: str, src: str | list[str]) -> None:
        """Ajoute/replace un stream dans l'instance go2rtc en cours. Accepte
        plusieurs sources (ex: Hikvision = flux vidéo RTSP + isapi:// séparé
        pour l'audio) combinées sous un seul nom de stream."""
        sources = src if isinstance(src, list) else [src]
        src_params = "&".join(f"src={quote(s, safe='')}" for s in sources)
        session = async_get_clientsession(self.hass)
        url = f"{self.base_url}api/streams?name={quote(name)}&{src_params}"
        async with session.put(url) as resp:
            if resp.status >= 300:
                body = await resp.text()
                raise Go2rtcUnavailable(
                    f"Échec enregistrement stream '{name}': {resp.status} {body}"
                )

    async def async_list_streams(self) -> list[str]:
        session = async_get_clientsession(self.hass)
        async with session.get(f"{self.base_url}api/streams") as resp:
            data = await resp.json(content_type=None)
            return list(data.keys())

    async def async_remove_stream(self, name: str) -> None:
        session = async_get_clientsession(self.hass)
        url = f"{self.base_url}api/streams?src={quote(name)}"
        async with session.delete(url):
            pass

    async def async_is_playing(self, camera: str) -> bool:
        """Une diffusion (live/file/tts) est active si un producteur temporaire
        s'ajoute à la source de base configurée pour cette caméra."""
        session = async_get_clientsession(self.hass)
        url = f"{self.base_url}api/streams?src={quote(camera)}"
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return False
                data = await resp.json(content_type=None)
        except Exception:  # noqa: BLE001
            return False
        producers = data.get("producers") or []
        return len(producers) > 1

    async def async_sync_cameras(self, cameras: list[dict]) -> dict[str, str]:
        """Enregistre chaque caméra indépendamment. Retourne {nom: erreur} pour
        celles qui ont échoué — une caméra en échec ne doit jamais bloquer les
        autres."""
        wanted = {cam["name"] for cam in cameras}
        existing = set(await self.async_list_streams())
        for stale in existing - wanted:
            await self.async_remove_stream(stale)

        errors: dict[str, str] = {}
        for cam in cameras:
            src = cam["stream_url"]
            if (
                isinstance(src, str)
                and cam.get("backchannel", True)
                and "#backchannel" not in src
            ):
                src = f"{src}#backchannel=1"
            try:
                await self.async_register_stream(cam["name"], src)
            except Go2rtcUnavailable as err:
                _LOGGER.error("Caméra '%s' non enregistrée: %s", cam["name"], err)
                errors[cam["name"]] = str(err)
        return errors

    async def async_play(self, camera: str, action: str, value: str) -> None:
        """action: 'file' ou 'live' (voir api/ffmpeg de go2rtc)."""
        session = async_get_clientsession(self.hass)
        url = (
            f"{self.base_url}api/ffmpeg?dst={quote(camera)}"
            f"&{action}={quote(value, safe='')}"
        )
        async with session.post(url) as resp:
            if resp.status >= 300:
                body = await resp.text()
                raise Go2rtcUnavailable(
                    f"Échec diffusion sur '{camera}': {resp.status} {body}"
                )

    async def async_stop_play(self, camera: str) -> None:
        """Arrête proprement la diffusion en cours sur cette caméra."""
        await self.async_play(camera, "file", str(SILENCE_FILE))
