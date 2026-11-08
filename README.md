# go2rtc Audio Diffusion

A Home Assistant custom integration to broadcast audio — text-to-speech,
uploaded/server audio files, or a live radio stream — onto two-way audio
cameras, independent of Frigate and independent of Home Assistant's built-in
go2rtc integration.

> ⚠️ **Custom / community development — use at your own risk.** This is not
> an official Home Assistant integration and is not affiliated with
> Home Assistant, Nabu Casa, or the go2rtc project. It is provided as-is,
> best-effort, with no warranty. See [License](#license).

## Why this exists

Home Assistant's own go2rtc integration doesn't support adding custom
streams, and routing audio through Frigate's go2rtc instance ties your
camera announcements to Frigate being up and typically requires a
long-lived access token. This integration runs its **own dedicated go2rtc
instance** (official binary from
[AlexxIT/go2rtc](https://github.com/AlexxIT/go2rtc)) directly inside Home
Assistant, on its own port, with no dependency on Frigate and **no access
token required** — TTS is resolved through Home Assistant Core's own public
media-source API.

## Features

- Dedicated go2rtc process, managed entirely by the integration (own binary
  download, own config, own API port) — no conflict with Frigate's go2rtc
  or Home Assistant's own.
- Per-camera entities: radio URL text field, TTS message text field, TTS
  engine selector, TTS voice selector (when the engine supports it), and
  buttons to broadcast radio / broadcast message / **stop**.
- A `binary_sensor` per camera showing whether a broadcast is currently
  active — so you know from inside the house whether the camera is
  currently talking.
- A `go2rtc_audio.diffuser` service for use in automations and scripts:
  radio stream, TTS message (with optional engine and voice), a file
  already in your media library, or a file uploaded through the service
  call UI.
- Camera setup helpers aimed at non-technical users:
  - **Local network scan** (standard ONVIF WS-Discovery, not a port scan)
    to help find a camera's IP address.
  - **Automatic brand detection** from an existing Home Assistant camera
    entity's manufacturer/model, to build the correct backchannel URL for
    you (you still always type the password yourself — credentials are
    never read from another integration).
  - A **manual brand picker** for cases where automatic detection can't
    work (for example, a camera exposed through an NVR like Frigate, which
    hides the real camera brand from Home Assistant).
  - A free-form custom RTSP/URL field as a fallback for anything not
    covered above.
- Bilingual: English (default) and French.

## Supported camera brands

| Brand | Mechanism | Confidence |
|---|---|---|
| Reolink | `rtsp://user:pass@host/Preview_01_sub#backchannel=1` | **Confirmed working** (tested) |
| Hikvision | RTSP video + separate `isapi://user:pass@host` audio source | Best-effort, **not tested** by the author |
| Dahua | `rtsp://user:pass@host/cam/realmonitor?...&unicast=true&proto=Onvif` | Best-effort, **not tested** by the author |
| Amcrest (Dahua OEM) | Same as Dahua | Best-effort, **not tested** by the author |
| Anything else | Custom URL field (manual) | You provide the full go2rtc source string |

These mechanisms come directly from
[go2rtc's own documentation](https://github.com/AlexxIT/go2rtc) for each
protocol, not from guesswork — but only Reolink has actually been verified
end-to-end by ear. If you test one of the "best-effort" brands successfully
(or unsuccessfully), please open an issue — real feedback is what moves
these from best-effort to confirmed.

## Installation

1. Copy `custom_components/go2rtc_audio/` into your Home Assistant
   `config/custom_components/` directory
2. Restart Home Assistant

## Setup

Settings → Devices & Services → **Add Integration** → "go2rtc Audio
Diffusion" → choose a dedicated API port (default `1985`, just needs to be
free on your machine).

Then, from the integration's **Configure** menu, **Add a camera**:

- Pick an existing camera entity for automatic detection, and/or
- Pick the brand yourself and fill the address found by the network scan
  (or type it in), with username/password, or
- Fill a fully custom URL if nothing above fits your setup

## Using the service

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

## Known limitations

- Automatic brand/host detection only works for a camera added to Home
  Assistant through a brand-specific integration (or well-populated ONVIF
  device info). A camera exposed through an NVR (Frigate, etc.) hides the
  real brand/model from Home Assistant — use the manual brand picker with
  the address found by the network scan instead.
- The `media_file` and `upload_file` service fields are implemented and
  schema-validated but have not yet been exercised through the real
  Home Assistant UI (their selectors can't be simulated by a direct
  service call during development).
- No automated test suite yet.

## Credits

Built on top of the excellent [go2rtc](https://github.com/AlexxIT/go2rtc)
project by AlexxIT. Not affiliated with or endorsed by that project.

## License

[MIT](LICENSE)
