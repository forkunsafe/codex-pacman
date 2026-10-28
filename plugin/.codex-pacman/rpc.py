"""Bounded, newline-delimited app-server RPC. No authentication payloads are read."""
import json
import os
import selectors
import subprocess
import time
from core import MonitorError

MAX_BUFFER = 1024 * 1024


class RPC:
    def __init__(self, binary, home, timeout=15, command=None):
        self.timeout = timeout
        self.sequence = 0
        self.buffer = b''
        self.process = None
        self.selector = selectors.DefaultSelector()
        env = dict(os.environ, CODEX_HOME=str(home))
        # Credentials belong to Codex's selected environment, never inherited API overrides.
        for key in ('OPENAI_API_KEY', 'OPENAI_ACCESS_TOKEN', 'CODEX_API_KEY'):
            env.pop(key, None)
        self.env = env
        self.command = command or [binary, 'app-server', '-c', 'analytics.enabled=false', '-c', 'otel.exporter="none"']

    def __enter__(self):
        try:
            self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL, env=self.env, bufsize=0)
            self.selector.register(self.process.stdout, selectors.EVENT_READ)
            self.request('initialize', {'clientInfo': {'name': 'codex_pacman', 'title': 'Codex Pac-Man', 'version': '1.0.1'}})
            self.send({'method': 'initialized'})
            return self
        except BaseException:
            self.close()
            raise

    def send(self, payload):
        try:
            self.process.stdin.write((json.dumps(payload) + '\n').encode())
        except (OSError, ValueError):
            raise MonitorError('Codex app-server stopped. Check the selected environment and update Codex CLI.') from None

    def request(self, method, params=None):
        self.sequence += 1
        request = {'id': self.sequence, 'method': method}
        if params is not None:
            request['params'] = params
        self.send(request)
        deadline = time.monotonic() + self.timeout
        while True:
            while b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                try:
                    value = json.loads(line)
                except (ValueError, UnicodeError):
                    raise MonitorError('Malformed response from Codex app-server. Try updating Codex CLI.') from None
                if not isinstance(value, dict):
                    raise MonitorError('Unsupported app-server message schema.')
                if 'method' in value and 'id' in value:
                    # Never fulfill server-initiated auth or permission requests.
                    self.send({'id': value['id'], 'error': {'code': -32601, 'message': 'Not supported by this read-only client'}})
                    continue
                if value.get('id') != self.sequence:
                    continue
                if 'error' in value:
                    error = value['error']
                    code = error.get('code') if isinstance(error, dict) else None
                    if code == -32601:
                        raise MonitorError('Codex app-server does not support this RPC. Update Codex CLI.')
                    raise MonitorError('Codex could not read quota. Check normal Codex login in the selected CODEX_HOME; API-key quotas may be unavailable. No login was initiated.')
                if 'result' not in value or not isinstance(value['result'], dict):
                    raise MonitorError('Unsupported app-server response schema.')
                return value['result']
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self.selector.select(remaining):
                raise MonitorError('Codex app-server timed out. Will retry automatically in one minute.')
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                raise MonitorError('Codex app-server exited before replying. Check Codex CLI and selected environment.')
            self.buffer += chunk
            if len(self.buffer) > MAX_BUFFER:
                raise MonitorError('Codex app-server response exceeded the safe size limit.')

    def close(self):
        self.selector.close()
        if self.process is None:
            return
        try:
            self.process.stdin.close()
            self.process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        finally:
            self.process.stdout.close()

    def __exit__(self, *_):
        self.close()
