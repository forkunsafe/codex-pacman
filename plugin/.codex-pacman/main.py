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
    # Trailing separators commit complete frames, even if pipe reads are split.
    sys.stdout.write(content + '~~~\n')
    sys.stdout.flush()


def stop(_signum, _frame):
    raise SystemExit(0)


def poll(home):
    with RPC(executable(), home) as rpc:
        return parse_limits(rpc.request('account/rateLimits/read'))


def run(once=False):
    env = os.environ
    name = env.get('VAR_DISPLAY_NAME', '').strip() or 'Codex'
    animate = env.get('VAR_ENABLE_ANIMATION', 'true').lower() == 'true'
    home = codex_home(env)
    instance = env.get('SWIFTBAR_PLUGIN_PATH', str(Path(__file__).resolve().parent.parent / 'codex-pacman.sh'))
    directory = state_directory(home, instance)
    # Hold the lock for the entire stream, preventing overlapping instances/RPC.
    with (directory / 'instance.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise MonitorError('Another instance is stopping. Will retry automatically; Refresh now retries sooner.') from None
        state = load_state(directory / 'state.json')
        windows, updated = state.get('windows', {}), state.get('updated', 0)
        emit(render(windows, updated, time.time(), name, 'Refreshing quota…'))
        certain = False  # A restart always establishes a new animation baseline.
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
                    # Commit before animation: a restart cannot replay this event.
                    save_state(directory / 'state.json', current, now)
                    windows, updated, certain = current, now, True
                    if play and animate and not once:
                        try:
                            for frame in animation_frames():
                                emit(render(windows, updated, time.time(), name, frame=frame))
                                time.sleep(.2)
                        finally:
                            emit(render(windows, updated, time.time(), name))
                    else:
                        emit(render(windows, updated, now, name))
                except (MonitorError, OSError):
                    exc = sys.exc_info()[1]
                    message = str(exc) if isinstance(exc, MonitorError) else 'Local I/O failed. Check Codex installation and plugin state-directory permissions.'
                    certain = False
                    emit(render(windows, updated, time.time(), name, message))
                if once:
                    return
                # Read bounded commands, no threads, no busy loops, no queued RPC.
                deadline = time.monotonic() + POLL_SECONDS
                pending = b''
                while True:
                    delay = max(0, deadline - time.monotonic())
                    events = selector.select(delay)
                    if not events:
                        break
                    data = os.read(sys.stdin.fileno(), 4096)
                    if not data:
                        selector.unregister(sys.stdin)
                        continue
                    pending = (pending + data)[-4096:]
                    if b'\n' in pending:
                        commands = pending.split(b'\n')
                        pending = commands.pop()
                        if b'refresh' in commands:
                            time.sleep(max(0, 2 - (time.monotonic() - request_started)))
                            break


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
            try:
                emit(render({}, 0, time.time(), os.environ.get('VAR_DISPLAY_NAME', 'Codex'), message))
            except BrokenPipeError:
                return
            if '--once' in sys.argv:
                return
            # Invalid settings also recover without restarting SwiftBar.
            with selectors.DefaultSelector() as selector:
                try:
                    selector.register(sys.stdin, selectors.EVENT_READ)
                except (OSError, ValueError):
                    pass
                if selector.select(POLL_SECONDS):
                    if not os.read(sys.stdin.fileno(), 4096):
                        time.sleep(POLL_SECONDS)


if __name__ == '__main__':
    main()
