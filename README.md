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

1. **Ad detection** — Every 5 seconds during normal playback (0.5 s during an ad), the script scans the screen for images stored in the `ads/` folder. When a match is found, it means an ad is playing.
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

---

## License

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

This project is licensed under the [Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/) license.

You are free to share and adapt this project for **non-commercial purposes**, as long as you give appropriate credit. Commercial use is not permitted.

