"""
Title: agent_guard
Description: Body of the NSSM service. The service runs in Session 0 and cannot see the desktop, so it only
keeps the scheduled task that runs the interactive agent alive (spotify-ad-mute.py --service).
"""

import argparse
import logging
import subprocess
import time

log = logging.getLogger('agent_guard')


def guard_step(task_state, now, last_start, cooldown) -> str:
    """'ok' | 'start' | 'waiting' | 'disabled' | 'missing' for the agent task's current state."""
    if task_state is None:
        return 'missing'
    if task_state == 'Disabled':
        return 'disabled'
    if task_state == 'Running':
        return 'ok'
    if last_start is not None and now - last_start < cooldown:
        return 'waiting'
    return 'start'


def task_state(name: str):
    """Scheduled task state ('Running', 'Ready', ...) or None if the task does not exist."""
    out = subprocess.run(['powershell', '-NoProfile', '-Command',
                          f"(Get-ScheduledTask -TaskName '{name}' -ErrorAction SilentlyContinue).State"],
                         capture_output=True, text=True).stdout.strip()
    return out or None


def start_task(name: str):
    subprocess.run(['schtasks', '/Run', '/TN', name], capture_output=True, text=True, check=True)


def main():
    parser = argparse.ArgumentParser(description="Keep the Spotify Ad Mute agent task running.")
    parser.add_argument('--task', default='SpotifyAdMute-Agent')
    parser.add_argument('--interval', type=float, default=15.0)
    parser.add_argument('--cooldown', type=float, default=60.0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    log.info("Guarding task '%s' every %.0f s", args.task, args.interval)
    last_start, last_action = None, None
    while True:
        action = guard_step(task_state(args.task), time.monotonic(), last_start, args.cooldown)
        if action == 'start':
            try:
                start_task(args.task)
                log.info("Agent task was not running: started it")
            except subprocess.CalledProcessError as exc:
                log.warning("Could not start the agent task (no logged-on user?): %s", (exc.stderr or '').strip())
            last_start = time.monotonic()
        elif action != last_action and action != 'ok':
            log.warning("Agent task: %s", action)
        last_action = action
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
