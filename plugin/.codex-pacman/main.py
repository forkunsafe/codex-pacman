#!/usr/bin/env python3
"""One idle streaming process; short-lived, serialized quota requests."""
import fcntl
import os
from pathlib import Path
import selectors
import signal
import sys
import time
from core import MonitorError, codex_home, consumed, executable, load_state, parse_limits, save_state, state_directory
from rpc import RPC
from ui import animation_frames, render

POLL_SECONDS = 60


def emit(content):
    sys.stdout.write(content + '~~~\n')
    sys.stdout.flush()


def stop(_signum, _frame):
    raise SystemExit(0)


def poll(home):
    with RPC(executable(), home) as rpc:
        return parse_limits(rpc.request('account/rateLimits/read'))


class Display:
    """Keep transient visual feedback separate from quota and persisted state."""
    def __init__(self, name, windows=None, updated=0, error=None):
        self.name = name
        self.windows = windows or {}
        self.updated = updated
        self.error = error

    def show(self, frame=None):
        emit(render(self.windows, self.updated, time.time(), self.name, self.error, frame))

    def animate(self):
        # Explicit preview also works when automatic animation is disabled.
        try:
            for frame in animation_frames():
                self.show(frame)
                time.sleep(frame[1])
        finally:
            self.show()


def wait_for_refresh(selector, request_started=None, display=None):
    """Preview does not fetch quota or postpone the polling deadline."""
    deadline = time.monotonic() + POLL_SECONDS
    pending = b''
    while True:
        now = time.monotonic()
        if now >= deadline:
            return
        events = selector.select(deadline - now)
        if not events:
            return
        data = os.read(sys.stdin.fileno(), 4096)
        if not data:
            selector.unregister(sys.stdin)
            continue
        pending = (pending + data)[-4096:]
        if b'\n' in pending:
            commands = pending.split(b'\n')
            pending = commands.pop()
            if b'refresh' in commands:
                if request_started is not None:
                    time.sleep(max(0, 2 - (time.monotonic() - request_started)))
                return
            if b'preview' in commands and display is not None:
                display.animate()


def run(once=False):
    env = os.environ
    name = env.get('VAR_DISPLAY_NAME', '').strip() or 'Codex'
    animate = env.get('VAR_ENABLE_ANIMATION', 'true').lower() == 'true'
    home = codex_home(env)
    instance = env.get('SWIFTBAR_PLUGIN_PATH', str(Path(__file__).resolve().parent.parent / 'codex-pacman.sh'))
    directory = state_directory(home, instance)
    with (directory / 'instance.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise MonitorError('Another instance is stopping. Will retry automatically; Refresh now retries sooner.') from None
        state = load_state(directory / 'state.json')
        windows, updated = state.get('windows', {}), state.get('updated', 0)
        display = Display(name, windows, updated, 'Refreshing quota…')
        display.show()
        certain = False
        with selectors.DefaultSelector() as selector:
            try:
                selector.register(sys.stdin, selectors.EVENT_READ)
            except (OSError, ValueError):
                pass
            while True:
                request_started = time.monotonic()
                try:
                    current = poll(home)
                    now = time.time()
                    play = consumed(windows, current, updated, now, certain)
                    save_state(directory / 'state.json', current, now)
                    windows, updated, certain = current, now, True
                    display.windows, display.updated, display.error = windows, updated, None
                    if play and animate and not once:
                        display.animate()
                    else:
                        display.show()
                except (MonitorError, OSError) as exc:
                    display.error = str(exc) if isinstance(exc, MonitorError) else 'Local I/O failed. Check Codex installation and plugin state-directory permissions.'
                    certain = False
                    display.show()
                if once:
                    return
                wait_for_refresh(selector, request_started, display)


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while True:
        try:
            run('--once' in sys.argv)
            return
        except BrokenPipeError:
            return
        except (MonitorError, OSError) as exc:
            message = str(exc) if isinstance(exc, MonitorError) else 'Cannot create private plugin state. Check your home-directory permissions.'
            display = Display(os.environ.get('VAR_DISPLAY_NAME', 'Codex'), error=message)
            try:
                display.show()
            except BrokenPipeError:
                return
            if '--once' in sys.argv:
                return
            with selectors.DefaultSelector() as selector:
                try:
                    selector.register(sys.stdin, selectors.EVENT_READ)
                except (OSError, ValueError):
                    pass
                wait_for_refresh(selector, display=display)


if __name__ == '__main__':
    main()
