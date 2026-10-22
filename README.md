# spotify-ad-mute

Automatically mutes Spotify whenever an ad is detected on screen, using image recognition. Supports both local sessions (via Windows Core Audio API) and remote desktop sessions (via on-screen volume icon click).

---

![demo](example.gif)

---

## Requirements

- Windows
- Python 3.10+
- Spotify desktop app (must be visible on screen, not minimised)

Install all dependencies:

```
pip install -r requirements.txt
```

Dependencies (`requirements.txt`):

```
pyautogui
pyscreeze
Pillow
opencv-python
pick
pycaw
```

---

## Usage

```
python spotify-ad-mute.py
```

Behaviour is controlled by two toggles at the top of the script (see [Configuration](#configuration) below).

### With menu enabled (`USE_MENU = True`, default)

1. Run the script.
2. Select **Run** using the arrow keys and press `Enter` — the muter starts in the background.
3. Select **Stop** to stop and exit.
4. Select **Diagnose** to run a one-shot check (see [Diagnosing issues](#diagnosing-issues)).

### Without menu (`USE_MENU = False`)

The muter starts immediately on launch. Press `Ctrl+C` to stop.
Recommended when you want clean log output for debugging.

---

## Service mode (`--service`)

```
python spotify-ad-mute.py --service [--images DIR] [--pycaw on|off] [--log FILE] [--no-autoplay] [--detect both|title|images]
```

Runs without a menu and keeps Spotify healthy while muting ads. Every 5 seconds it:

- launches Spotify if it is not running (the install is found through the registry, then `%APPDATA%\Spotify`),
- keeps the Spotify window maximized,
- checks that the volume icon is visible and, if not, brings the window to the front and then hovers the player bar. The retries back off (10 s, then 20 s, 40 s and so on up to 5 minutes) so a window that never shows its controls is not poked every few seconds,
- restarts Spotify when the volume icon has been missing for 3 minutes in a row (a blank or crashed UI, for example "Something went wrong", still answers Windows messages, so the "not responding" check cannot see it). It does this at most 3 times until the icon is seen again, so a screen where the icon images do not match cannot cause an endless restart loop,
- does nothing while the screen is locked, and after a sleep or an unlock it starts its timers again from zero, so closing and reopening a laptop lid continues the session where it left off (Spotify is not restarted and playback is not touched),
- resets the muter state when Spotify restarts,
- starts playback when Spotify (re)starts, if nothing is playing (it sends a *play* command to Spotify's window, not the play/pause key, so it never pauses music that is already playing and cannot reach another player).

It needs a logged-on desktop session, because it reads the screen and moves the mouse. While the screen is locked it waits (see above); ads that start during a lock are not muted by the click method.
Logs go to a rotating file, `%LOCALAPPDATA%\spotify-ad-mute\agent.log` unless `--log` is given.

| Option | Meaning |
|---|---|
| `--images DIR` | Per-machine images: `DIR/volume/volume.png` and `mute.png` replace the repo's icons, `DIR/ads/*` are added to the ads |
| `--pycaw on\|off` | Overrides `USE_PYCAW` for this run |
| `--log FILE` | Log file |
| `--no-autoplay` | Do not start playback when Spotify (re)starts |
| `--detect MODE` | Ad detection: `title` = window title + audio state (no screen scan), `images` = screen images only, `both` (default) = title and audio first, images only when those cannot decide |

---

## Run at Windows start (NSSM)

A service runs in Session 0 and cannot see the desktop, so the setup has two parts (run from an elevated shell, see `service/`):

- a **logon task** (`SpotifyAdMute-Agent`) that runs `spotify-ad-mute.py --service` in the user's session, and
- an **NSSM service** (`SpotifyAdMute`, delayed auto-start) that starts with Windows and keeps that task running.

```
service\install-service.ps1 -Nssm C:\tools\nssm.exe -Python C:\Python312\python.exe -User YourUser [-ImagesDir DIR] [-Pycaw on|off] [-DryRun]
service\uninstall-service.ps1 -Nssm C:\tools\nssm.exe
```

Both are safe to run again. Prerequisites: NSSM, a Python with `requirements.txt` installed that SYSTEM can read, and
**auto-logon with no screen saver or lock** (Sysinternals Autologon), since the agent reads the screen. The installer warns
when auto-logon or the screen saver settings are wrong. Logs: `%LOCALAPPDATA%\spotify-ad-mute\agent.log` (agent) and
`%ProgramData%\spotify-ad-mute\service.log` (service).

---

## Configuration

Open `spotify-ad-mute.py` and adjust these flags near the top of the file:

```python
# Set to True to show the interactive pick menu (Run / Stop / Diagnose).
# Set to False to start the muter immediately without any UI.
USE_MENU = True

# Set to True to enable verbose DEBUG-level logging.
# Useful for diagnosing image detection and mute state issues.
DEBUG_LOGGING = False

# Set to True to mute via the Windows Core Audio API (pycaw) — works locally.
# Set to False to mute by clicking Spotify's on-screen volume icon — useful for
# remote desktop sessions where pycaw only affects the local audio session.
USE_PYCAW = True
```

### Choosing the right mute method

| `USE_PYCAW` | Method | Best for |
|---|---|---|
| `True` (default) | Mutes the `Spotify.exe` audio session directly via Windows Core Audio | Local sessions |
| `False` | Clicks Spotify's on-screen volume icon to toggle mute | Remote desktop / RDP, where pycaw only affects the local machine's audio stack |

> **Note:** When `USE_PYCAW = False`, the `volume/` images must be correctly captured for your setup, since the script locates the icon on screen before clicking it.

---

## How it works

1. **Ad detection** — Unless `--detect images` is used, the window title decides first: `Artist - Song` means a track is playing (no ad, no scan); any other title is an ad while Spotify is producing sound or after the muter has silenced it, which keeps the ad break muted until a track title returns. A silent, unmuted player with such a title is a pause, and only the image scan (when enabled) can tell. Every 5 seconds during normal playback (0.5 s during an ad), the script scans the screen for images stored in the `ads/` folder. When a match is found, it means an ad is playing.
2. **Mute control** — Depending on `USE_PYCAW`:
   - `True`: The Windows Core Audio API (`pycaw`) mutes/unmutes the Spotify process directly — no mouse interaction required.
   - `False`: The script locates Spotify's volume icon on screen and clicks it to toggle mute — works across remote desktop sessions where pycaw cannot reach the remote audio stack.
3. **Mute state sync** — Each cycle checks the `volume/` images to read Spotify's on-screen volume icon state, keeping internal state in sync even if the user mutes manually.

---

## Image setup — important for your resolution

The script relies on pixel-level image matching. The reference images in `ads/` and `volume/` were captured at a specific screen resolution and DPI scaling. If detection doesn't work on your machine, you will need to **retake the screenshots at your own resolution**.

### `ads/` folder
Contains screenshots of Spotify's UI **while an ad is playing** (the ad banner/label area). Add as many variants as needed (English, other languages, different ad formats).

**How to capture:**
1. Wait for a Spotify ad to appear.
2. Take a cropped screenshot of the ad indicator area (the small label or banner that appears during ads — not the ad artwork itself).
3. Save it as a `.png` into the `ads/` folder.

### `volume/` folder
Contains two screenshots of Spotify's volume button:

| File | When to capture |
|---|---|
| `volume.png` | Spotify is **unmuted** — capture the speaker icon in its normal state |
| `mute.png` | Spotify is **muted** — capture the crossed-out speaker icon |

**How to capture:**
1. Make sure Spotify is visible and unobstructed.
2. Take a tightly cropped screenshot of just the volume/mute icon.
3. Replace the existing `volume.png` / `mute.png`.

> **Tip:** If images are detected inconsistently, try lowering the confidence threshold in `locate_image()` from `0.9` to `0.8` or `0.75`.

---

## Diagnosing issues

Select **Diagnose** from the menu (requires `USE_MENU = True`), or set `DEBUG_LOGGING = True` for verbose output. The diagnostic will report:

- Which mute method is active (`USE_PYCAW`).
- Whether pycaw can find the Spotify audio session.
- Whether each image file exists on disk.
- Whether each ad image matches anything currently on screen.
- The detected on-screen mute state (muted / unmuted / unknown).

---

## Known limitations

- Spotify must be on the main screen and fully visible (not minimised or covered).
- Reference images in `ads/` and `volume/` must match your screen resolution and Windows DPI scaling. Retake them if detection fails.
- When using `USE_PYCAW = True`: the Spotify audio session must be active (producing sound) for pycaw to find it.
- When using `USE_PYCAW = False`: Spotify's volume icon must be visible and unobstructed for click-based muting to work.
- Service mode needs a logged-on desktop (auto-logon helps after a reboot): it reads the screen and moves the mouse, and it pauses while the screen is locked. The service itself does not start the agent before a user logs in.
- The 3-minute "controls missing" restart assumes the icon images match your screen. If they do not (see `--images`), Spotify is restarted up to 3 times before the agent leaves it alone, which interrupts the music.
- Autoplay sends *play* up to 3 times after Spotify starts and gives up if no track title appears (for example when Spotify has nothing to resume). It will also resume music you paused on purpose whenever Spotify or the agent restarts.
- With `--detect title` ad detection does not use images. In the default `both` mode images remain a fallback, and they depend on resolution and DPI (use `--images` for per-machine images); the image scan used about a third of one CPU core on the test machine (Windows 10, 1920x1080), but now only runs when the title and audio cannot decide.
- Only the classic desktop install is supported (found through the registry, then `%APPDATA%\Spotify`), not the Microsoft Store version.
- Do not run another ad muter at the same time: two muters clicking the same mute button cancel each other.

---

## License

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

This project is licensed under the [Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/) license.

You are free to share and adapt this project for **non-commercial purposes**, as long as you give appropriate credit. Commercial use is not permitted.

