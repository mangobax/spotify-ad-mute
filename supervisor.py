"""
Title: supervisor
Description: Decides when Spotify must be (re)launched. Pure logic plus a Windows probe.
"""

import csv
import ctypes
import os
import subprocess
import time
from pathlib import Path
from ctypes import wintypes


def spotify_probe() -> tuple[bool, int | None]:
    """Return (process_alive, hwnd): any Spotify.exe running, and its visible titled top-level window."""
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Spotify.exe', '/FO', 'CSV', '/NH'],
                         capture_output=True, text=True, errors='replace').stdout
    pids = {int(r[1]) for r in csv.reader(l for l in out.splitlines() if l.startswith('"'))
            if r[0].lower() == 'spotify.exe'}
    if not pids:
        return False, None

    user32, found = ctypes.windll.user32, []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(visit, 0)
    return True, (found[0] if found else None)


def spotify_path(env=os.environ) -> Path:
    """Classic desktop install location."""
    return Path(env['APPDATA']) / 'Spotify' / 'Spotify.exe'


def launch_spotify(path: Path | None = None):
    """Start Spotify detached from this process. Run it in the user's session, not from a service."""
    subprocess.Popen([str(path or spotify_path())], creationflags=0x00000008 | 0x00000200)  # DETACHED_PROCESS | NEW_PROCESS_GROUP


# --- Maximized window ---

def window_is_maximized(hwnd: int) -> bool:
    user32 = ctypes.windll.user32
    return bool(user32.IsZoomed(hwnd)) and not user32.IsIconic(hwnd)


def show_window(hwnd: int, cmd: int):
    ctypes.windll.user32.ShowWindow(hwnd, cmd)


def ensure_maximized(hwnd: int, is_maximized=window_is_maximized, show=show_window) -> str:
    """Return 'ok' or 'maximized'. SW_MAXIMIZE is idempotent and also restores a minimized window,
    so no keys, focus or settle time are needed."""
    if is_maximized(hwnd):
        return 'ok'
    show(hwnd, 3)  # SW_MAXIMIZE
    return 'maximized'


class Supervisor:
    """tick() returns 'ok' | 'starting' | 'waiting' | 'launched'.

    Spotify counts as ready only when its window exists. A process without a window (tray, hung, still
    loading) gets `startup_grace` seconds, then launch() is called again: Spotify.exe raises the window
    of the running instance. Relaunches back off exponentially until the window is ready.
    `generation` increments every time Spotify becomes ready again, so callers can reset their state.
    """

    def __init__(self, probe=spotify_probe, launch=None, now=time.monotonic,
                 startup_grace=30.0, backoff_base=5.0, backoff_max=300.0):
        self._probe, self._launch, self._now = probe, launch, now
        self._grace, self._base, self._max = startup_grace, backoff_base, backoff_max
        self.generation = 0
        self._ready = False
        self._attempts = 0
        self._last_launch = None
        self._since = None   # start of the current not-ready episode, or of the last launch

    def tick(self) -> str:
        alive, hwnd = self._probe()
        now = self._now()
        if hwnd is not None:
            if not self._ready:
                self._ready = True
                self.generation += 1
            self._attempts = 0
            return 'ok'
        if self._ready or self._since is None:
            self._ready = False
            self._since = now
        if alive and now - self._since < self._grace:
            return 'starting'
        if self._attempts and now - self._last_launch < min(self._base * 2 ** (self._attempts - 1), self._max):
            return 'waiting'
        self._launch()
        self._attempts += 1
        self._last_launch = self._since = now
        return 'launched'
