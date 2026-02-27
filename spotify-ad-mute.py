"""
Title: spotify-ad-mute
Description: This is a program to mute spotify whenever an ad appears.
Author: MANGOBA
Version: 27-Feb-2026
"""

try:
    import os
    import sys
    import time
    import logging
    from pathlib import Path
    from threading import Thread
    from pyautogui import locateCenterOnScreen, click as pyautogui_click
    from pick import pick
    from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
except ImportError as details:
    print("-E- Couldn't import module, try pip install 'module'")
    raise details


# --- Logging setup ---
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)

# --- Config ---
# Set to False to skip the pick menu and start the muter immediately.
# Useful when debugging, so log output is not obscured by the menu UI.
USE_MENU = True

# Set to True to enable verbose DEBUG-level logging.
# Useful for diagnosing detection and mute state issues.
DEBUG_LOGGING = False

# Set to True to mute via the Windows Core Audio API (pycaw) — works locally.
# Set to False to mute by clicking Spotify's on-screen volume icon — useful for
# remote desktop sessions where pycaw only affects the local audio session.
USE_PYCAW = True

log.setLevel(logging.DEBUG if DEBUG_LOGGING else logging.INFO)


# --- Path helpers ---

def resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    base_path = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    return base_path / relative_path


def collect_ad_images(folder: Path) -> list[Path]:
    """Return all PNG/JPG images found in the given ads folder."""
    images = [p for p in folder.iterdir() if p.suffix.lower() in {'.png', '.jpg', '.jpeg'}]
    if not images:
        log.warning("No ad images found in '%s'", folder)
    else:
        log.info("Loaded %d ad image(s) from '%s'", len(images), folder)
    return images


image_volume: Path = resource_path('volume/volume.png')
image_mute:   Path = resource_path('volume/mute.png')
image_ads:   list[Path] = collect_ad_images(resource_path('ads'))


# --- Audio control ---

def _mute_via_pycaw(muted: bool) -> bool:
    """Mute or unmute Spotify via the Windows Core Audio API.

    Returns True if the Spotify session was found and updated.
    """
    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        if session.Process and session.Process.name().lower() == 'spotify.exe':
            volume: ISimpleAudioVolume = session.SimpleAudioVolume
            volume.SetMute(muted, None)
            log.info("Spotify %s (pycaw)", "muted" if muted else "unmuted")
            return True
    log.warning("Spotify process not found; could not %s", "mute" if muted else "unmute")
    return False


def _mute_via_click(muted: bool) -> bool:
    """Mute or unmute Spotify by clicking its on-screen volume icon.

    Looks for the icon that represents the CURRENT state and clicks it to toggle.
    Returns True if the icon was found and clicked.
    """
    # If we want to mute, Spotify must currently be unmuted — look for volume icon.
    # If we want to unmute, Spotify must currently be muted — look for mute icon.
    target_image = image_volume if muted else image_mute
    target_label = "volume" if muted else "mute"
    pos = locate_image(target_image)
    if pos is not None:
        pyautogui_click(x=pos[0], y=pos[1], clicks=1, button='left')
        log.info("Spotify %s (clicked %s icon at %s)", "muted" if muted else "unmuted", target_label, pos)
        return True
    log.warning("Could not %s: '%s' icon not found on screen", "mute" if muted else "unmute", target_label)
    return False


def set_spotify_mute(muted: bool) -> bool:
    """Mute or unmute Spotify using whichever method is configured (USE_PYCAW)."""
    if USE_PYCAW:
        return _mute_via_pycaw(muted)
    else:
        return _mute_via_click(muted)


# --- Screen detection ---

def locate_image(image: Path):
    """Locate an image on screen. Returns center (x, y) or None."""
    try:
        return locateCenterOnScreen(str(image), grayscale=True, confidence=0.9)
    except Exception as exc:
        log.debug("locate_image failed for '%s': %s", image.name, exc)
        return None


def is_muted_on_screen() -> bool | None:
    """Check Spotify's on-screen mute state using the volume folder images.

    Returns True if mute icon is visible, False if volume icon is visible,
    or None if neither could be found (Spotify not visible / minimised).
    """
    if locate_image(image_mute) is not None:
        return True
    if locate_image(image_volume) is not None:
        return False
    return None  # Spotify UI not visible


def check_for_ad(ads: list[Path]):
    """Return the screen position of the first matching ad image, or None."""
    for ad in ads:
        log.debug("Checking ad image: '%s'", ad.name)
        pos = locate_image(ad)
        if pos is not None:
            log.info("Ad detected via image '%s' at %s", ad.name, pos)
            return pos
    return None


def diagnose():
    """Run a one-shot diagnostic: check pycaw finds Spotify, then scan for ads."""
    log.info("--- DIAGNOSE START ---")
    log.info("Mute method: %s", "pycaw (Windows Core Audio)" if USE_PYCAW else "UI click (on-screen volume icon)")

    # 1. Check pycaw can see Spotify
    sessions = AudioUtilities.GetAllSessions()
    names = [s.Process.name() for s in sessions if s.Process]
    log.info("Active audio sessions: %s", names)
    spotify_found = any(n.lower() == 'spotify.exe' for n in names)
    log.info("Spotify audio session found: %s", spotify_found)

    # 2. Check on-screen mute state via volume images
    screen_muted = is_muted_on_screen()
    if screen_muted is True:
        log.info("On-screen mute state: MUTED (mute icon visible)")
    elif screen_muted is False:
        log.info("On-screen mute state: UNMUTED (volume icon visible)")
    else:
        log.warning("On-screen mute state: UNKNOWN (neither icon found — is Spotify visible?)")

    # 2. Check ad images exist on disk
    log.info("Ad images loaded: %d", len(image_ads))
    for p in image_ads:
        log.info("  %s  exists=%s", p.name, p.exists())

    # 3. Try screen detection for each ad image
    log.info("Running screen scan for each ad image...")
    any_found = False
    for p in image_ads:
        pos = locate_image(p)
        if pos is not None:
            log.info("  FOUND '%s' at %s", p.name, pos)
            any_found = True
        else:
            log.info("  NOT found: '%s'", p.name)
    if not any_found:
        log.info("No ad images matched on screen. Is Spotify showing an ad right now?")

    log.info("--- DIAGNOSE END ---")


# --- Worker thread ---

class MuteAd(Thread):
    # How long to sleep between checks depending on ad state
    SLEEP_AD_ACTIVE  = 0.5   # seconds — poll quickly while ad is playing
    SLEEP_AD_IDLE    = 5.0   # seconds — poll slowly during normal playback

    def __init__(self):
        super().__init__(daemon=True)
        self.program_running = True
        self.running = False
        self._muted = False

    def run(self):
        while self.program_running:
            if not self.running:
                time.sleep(0.2)
                continue

            log.debug("Scanning screen for ads... (muted=%s)", self._muted)
            ad_pos = check_for_ad(image_ads)

            # Sync internal state with what Spotify actually shows on screen
            screen_muted = is_muted_on_screen()
            if screen_muted is not None and screen_muted != self._muted:
                log.debug("Mute state corrected from screen: %s -> %s", self._muted, screen_muted)
                self._muted = screen_muted

            if ad_pos is not None:
                # Ad is playing — mute if not already muted
                if not self._muted:
                    log.info("Ad detected — muting Spotify")
                    if set_spotify_mute(True):
                        self._muted = True
                time.sleep(self.SLEEP_AD_ACTIVE)
            else:
                log.debug("No ad on screen.")
                # No ad — unmute if we were the ones who muted
                if self._muted:
                    log.info("Ad gone — unmuting Spotify")
                    if set_spotify_mute(False):
                        self._muted = False
                time.sleep(self.SLEEP_AD_IDLE)

    def stop(self):
        """Signal the thread to exit cleanly, and unmute if needed."""
        self.running = False
        self.program_running = False
        if self._muted:
            set_spotify_mute(False)
            self._muted = False


# --- Menu ---

def show_menu(mute_ad: MuteAd) -> bool:
    """Display the interactive menu. Returns True when the user chooses Stop."""
    title = f'spotify-ad-mute: (({mute_ad.running}))'
    options = ['Run', 'Stop', 'Diagnose']
    _, index = pick(options, title)

    if index == 0:
        mute_ad.running = True
        log.info("Muter started")
    elif index == 1:
        mute_ad.stop()
        log.info("Muter stopped")
        return True
    elif index == 2:
        os.system('mode con cols=120 lines=40')
        diagnose()
        input("\nPress Enter to return to menu...")
        os.system('mode con cols=30 lines=7')
    return False


# --- Entry point ---

def main():
    mute_ad = MuteAd()
    mute_ad.start()

    try:
        if USE_MENU:
            os.system('mode con cols=30 lines=7')
            while True:
                if show_menu(mute_ad):
                    break
        else:
            log.info("Menu disabled (USE_MENU=False). Muter running — press Ctrl+C to stop.")
            mute_ad.running = True
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        log.info("Interrupted by user.")
    finally:
        mute_ad.stop()
        mute_ad.join()


if __name__ == "__main__":
    main()
