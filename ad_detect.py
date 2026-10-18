"""
Title: ad_detect
Description: Tells whether Spotify is playing an ad from its window title and audio, without scanning the screen.
"""

from supervisor import is_track_title


def spotify_audio_active() -> bool:
    """True when a Spotify audio session is actively rendering sound (Core Audio session state 'active')."""
    from pycaw.pycaw import AudioUtilities
    return any(s.State == 1 for s in AudioUtilities.GetAllSessions()
               if s.Process and s.Process.name().lower() == 'spotify.exe')


class AdDetector:
    """is_ad() combines the window title, the audio state and, as a fallback, an image scan.

    - A title 'Artist - Song' means a track is playing: never an ad, and no scan is needed.
    - Any other title (ad text, 'Spotify Free') is an ad while audio is flowing, or while we have muted Spotify
      ourselves: our own mute silences the meter, so `muted` keeps the ad break alive until a track title shows
      up (it also covers the silent gap between two ads).
    - A non-track title in silence without our mute is a pause or an idle player: only the image scan can tell,
      and image_check=None (title-only mode) means "not an ad".
    A failing title or audio source degrades to the image scan instead of raising.
    """

    def __init__(self, title, audio_active=spotify_audio_active):
        self._title, self._audio_active = title, audio_active

    def is_ad(self, muted: bool, image_check=None) -> bool:
        try:
            title = self._title()
            if title and is_track_title(title):
                return False
            if title and (muted or self._audio_active()):
                return True
        except Exception:
            pass
        return bool(image_check()) if image_check else False
