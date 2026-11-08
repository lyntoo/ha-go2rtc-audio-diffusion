"""Constantes — go2rtc Audio Diffusion."""

DOMAIN = "go2rtc_audio"

# Version du binaire go2rtc officiel (AlexxIT/go2rtc) à télécharger.
# Vérifier https://github.com/AlexxIT/go2rtc/releases avant de mettre à jour.
GO2RTC_VERSION = "1.9.15"

# Port API dédié, distinct de 1984 (go2rtc de Frigate / instance orpheline existante)
# et de 11984 (go2rtc natif HA en mode debug_ui).
DEFAULT_API_PORT = 1985
CONF_API_PORT = "api_port"

CONF_CAMERAS = "cameras"
CONF_CAMERA_NAME = "name"
CONF_CAMERA_URL = "stream_url"
CONF_CAMERA_BACKCHANNEL = "backchannel"
CONF_CAMERA_BRAND = "brand"
CONF_CAMERA_CONFIDENCE = "confidence"

ATTR_CAMERA_ENTITY = "camera_entity"
ATTR_CAMERA_BRAND_CHOICE = "brand_choice"
ATTR_CAMERA_HOST = "host"
ATTR_CAMERA_USERNAME = "username"
ATTR_CAMERA_PASSWORD = "password"

CONFIDENCE_CONFIRMED = "confirme"
CONFIDENCE_BEST_EFFORT = "best_effort"

SERVICE_DIFFUSER = "diffuser"

ATTR_CAMERA = "camera"
ATTR_RADIO_URL = "radio_url"
ATTR_MESSAGE = "message"
ATTR_MOTEUR_TTS = "moteur_tts"
ATTR_VOICE = "voice"
ATTR_MEDIA_FILE = "media_file"
ATTR_UPLOAD_FILE = "upload_file"

DEFAULT_TTS_ENGINE = "tts.piper"
# Option affichée quand aucune voix précise n'est choisie (ou que le moteur
# TTS actuel ne supporte pas le choix de voix) : on laisse le moteur décider.
DEFAULT_VOICE_OPTION = "(par défaut du moteur)"

# Table des binaires officiels go2rtc par plateforme (noms d'assets GitHub)
# https://github.com/AlexxIT/go2rtc/releases
GO2RTC_ASSETS = {
    ("Linux", "x86_64"): "go2rtc_linux_amd64",
    ("Linux", "aarch64"): "go2rtc_linux_arm64",
    ("Linux", "armv7l"): "go2rtc_linux_armv6",
    ("Linux", "i686"): "go2rtc_linux_i386",
    ("Darwin", "x86_64"): "go2rtc_mac_amd64.zip",
    ("Darwin", "arm64"): "go2rtc_mac_arm64.zip",
}
