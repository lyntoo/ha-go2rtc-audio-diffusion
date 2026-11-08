# go2rtc Audio Diffusion for Home Assistant

A custom Home Assistant integration to broadcast audio — text-to-speech, uploaded/server audio files, or a live radio stream — onto **two-way audio cameras**, running its own dedicated go2rtc instance, independent of Frigate and independent of Home Assistant's built-in go2rtc integration.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=go2rtc_audio)

---

## Why

Home Assistant's own go2rtc integration doesn't support adding custom streams, and routing camera announcements through Frigate's go2rtc instance ties them to Frigate being up, and typically requires a long-lived access token. This integration runs its **own dedicated go2rtc process** (the official binary from [AlexxIT/go2rtc](https://github.com/AlexxIT/go2rtc), downloaded and managed automatically), on its own port, with no dependency on Frigate and **no access token required** — TTS is resolved through Home Assistant Core's own public media-source API.

---

## Features

- **Fully independent go2rtc instance** — own binary, own config, own API port, no conflict with Frigate's go2rtc or Home Assistant's own
- **No long-lived access token** — TTS audio is resolved through Home Assistant's own internal media-source API
- **Per-camera entities:**
  - `text` — radio URL
  - `text` — TTS message
  - `select` — TTS engine (lists every TTS engine installed on your instance)
  - `select` — TTS voice (populated automatically when the chosen engine supports multiple voices)
  - `button` — Broadcast radio / Broadcast message / **Stop** (cleanly interrupts the current broadcast, no audible workaround message)
  - `binary_sensor` — Broadcast active (so you know from inside the house whether the camera is currently talking)
- **`go2rtc_audio.diffuser` service** for automations and scripts — live radio, TTS message (with optional engine and voice), a file already in your media library, or a file uploaded through the service call UI
- **Camera setup helpers, aimed at non-technical users:**
  - Local network scan (standard ONVIF WS-Discovery, not a port scan) to help find a camera's IP address
  - Automatic brand detection from an existing Home Assistant camera entity's manufacturer/model, to build the correct backchannel URL — you still always type the password yourself, credentials are never read from another integration
  - A manual brand picker for when automatic detection can't work (for example, a camera exposed through an NVR like Frigate, which hides the real camera brand from Home Assistant)
  - A free-form custom RTSP/URL field as a fallback for anything not covered above
- **Bilingual** — English (default) and French

---

## Supported camera brands

| Brand | Mechanism | Confidence |
|---|---|---|
| Reolink | `rtsp://user:pass@host/Preview_01_sub#backchannel=1` | **Confirmed working** (tested) |
| Hikvision | RTSP video + separate `isapi://user:pass@host` audio source | Best-effort, **not tested** by the author |
| Dahua | `rtsp://user:pass@host/cam/realmonitor?...&unicast=true&proto=Onvif` | Best-effort, **not tested** by the author |
| Amcrest (Dahua OEM) | Same as Dahua | Best-effort, **not tested** by the author |
| Anything else | Custom URL field (manual) | You provide the full go2rtc source string |

These mechanisms come directly from [go2rtc's own documentation](https://github.com/AlexxIT/go2rtc) for each protocol, not from guesswork — but only Reolink has actually been verified end-to-end by ear. If you test one of the "best-effort" brands, successfully or not, please open an issue.

---

## Requirements

- Home Assistant Core, with the `tts`, `media_source`, and `file_upload` components enabled (default)
- At least one two-way audio camera reachable on your network
- A camera brand/model supported above, or a known RTSP backchannel source to enter manually

---

## Installation

1. Copy the `custom_components/go2rtc_audio` folder into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

---

## Setup

1. Click the badge above, or go to **Settings → Devices & services → Add Integration**, search for **go2rtc Audio Diffusion**
2. Choose a dedicated API port (default `1985` — just needs to be free on your machine)
3. From the integration's **Configure** menu, **Add a camera**:
   - Pick an existing camera entity for automatic detection, and/or
   - Pick the brand yourself and fill in the address found by the network scan (or type it in), with username/password, or
   - Fill in a fully custom URL if nothing above fits your setup

---

## Uninstalling

**Settings → Devices & services → go2rtc Audio Diffusion → ⋮ → Delete**, then remove the `custom_components/go2rtc_audio` folder. The dedicated go2rtc binary and its config, downloaded automatically into Home Assistant's storage, can be removed from `config/go2rtc_audio/` as well. No credentials are stored by this integration beyond what you type directly into its own camera fields.

---

## Using the service in automations

```yaml
action: go2rtc_audio.diffuser
data:
  camera: front_door
  message: "Someone is at the door."
  moteur_tts: tts.piper
```

Or for a live radio stream:

```yaml
action: go2rtc_audio.diffuser
data:
  camera: front_door
  radio_url: "https://example.com/stream.mp3"
```

---

## Known limitations

- Automatic brand/host detection only works for a camera added to Home Assistant through a brand-specific integration (or well-populated ONVIF device info). A camera exposed through an NVR (Frigate, etc.) hides the real brand/model from Home Assistant — use the manual brand picker together with the address found by the network scan instead.
- The `media_file` and `upload_file` service fields are implemented and schema-validated but have not yet been exercised through the real Home Assistant UI (their selectors can't be simulated by a direct service call during development).
- No automated test suite yet.

---

## Credits

Built on top of the excellent [go2rtc](https://github.com/AlexxIT/go2rtc) project by AlexxIT. Not affiliated with or endorsed by that project.

---

## Disclaimer

This is a **custom, community-developed integration** — not an official Home Assistant integration, and not affiliated with Home Assistant, Nabu Casa, or the go2rtc project. It is provided as-is, best-effort, with no warranty. Use at your own risk.
