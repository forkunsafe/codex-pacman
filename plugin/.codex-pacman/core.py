"""Configuration, conservative quota parsing, and minimal atomic state."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile


class MonitorError(Exception):
    """A deliberately non-sensitive, user-facing error."""


def codex_home(env):
    selected = env.get('VAR_CODEX_HOME', '').strip() or env.get('CODEX_HOME', '').strip() or '~/.codex'
    path = Path(selected).expanduser()
    if not path.is_absolute():
        raise MonitorError('Codex Home must be an absolute path (or begin with ~).')
    if not path.is_dir():
        raise MonitorError('Selected Codex Home does not exist. Set Codex Home in SwiftBar settings; no fallback was attempted.')
    return path.resolve()


def executable():
    candidates = [shutil.which('codex'), '/opt/homebrew/bin/codex', '/usr/local/bin/codex']
    for value in candidates:
        if value and os.path.isfile(value) and os.access(value, os.X_OK):
            return value
    raise MonitorError('Codex CLI not found. Install it with: brew install --cask codex. Then refresh this plugin.')


def number(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def parse_limits(result):
    if not isinstance(result, dict) or 'rateLimits' not in result:
        raise MonitorError('Unsupported Codex quota response. Update Codex Pac-Man or Codex CLI.')
    buckets = result.get('rateLimitsByLimitId')
    if buckets is not None:
        if not isinstance(buckets, dict):
            raise MonitorError('Unsupported Codex quota bucket schema.')
        bucket = buckets.get('codex')
    else:
        bucket = result['rateLimits']
    if bucket is None:
        raise MonitorError('Codex quota is unavailable for this account or authentication type.')
    if not isinstance(bucket, dict) or bucket.get('limitId') not in (None, 'codex'):
        raise MonitorError('No ordinary Codex quota bucket is available.')
    windows = {}
    for slot in ('primary', 'secondary'):
        item = bucket.get(slot)
        if item is None:
            continue
        if not isinstance(item, dict) or not number(item.get('usedPercent')):
            raise MonitorError('Unsupported Codex quota window schema.')
        used = item['usedPercent']
        duration, reset = item.get('windowDurationMins'), item.get('resetsAt')
        if not 0 <= used <= 100:
            raise MonitorError('Codex returned an invalid usage percentage.')
        if duration is not None and (not number(duration) or duration <= 0):
            raise MonitorError('Codex returned an invalid window duration.')
        if reset is not None and (not number(reset) or not 0 <= reset <= 253402300799):
            raise MonitorError('Codex returned an invalid reset timestamp.')
        windows[slot] = {'used': used, 'duration': duration, 'reset': reset}
    if not windows:
        raise MonitorError('No quota windows available. API-key accounts may not expose ChatGPT quotas.')
    return windows


def consumed(previous, current, last_success, now, certain):
    if not certain or not previous or not 0 <= now - last_success <= 90:
        return False
    event = False
    for slot, new in current.items():
        old = previous.get(slot)
        if not old or new['duration'] is None or new['reset'] is None:
            continue
        if old['duration'] != new['duration'] or old['reset'] != new['reset']:
            continue
        if new['reset'] <= now or new['used'] < old['used']:
            continue
        event |= math.floor(new['used']) > math.floor(old['used'])
    return event


def state_directory(home, instance):
    instance_id = hashlib.sha256(str(instance).encode()).hexdigest()[:24]
    home_id = hashlib.sha256(str(home).encode()).hexdigest()[:24]
    root = Path.home() / 'Library' / 'Application Support' / 'Codex Pac-Man' / instance_id / home_id
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def load_state(path):
    try:
        if path.stat().st_size > 16384:
            return {}
        value = json.loads(path.read_text())
        if value.get('version') != 1 or not number(value.get('updated')) or not 0 <= value['updated'] <= 253402214399:
            return {}
        # Reuse the strict parser to validate cached data before displaying it.
        windows = value['windows']
        raw = {k: {'usedPercent': v['used'], 'windowDurationMins': v['duration'], 'resetsAt': v['reset']} for k, v in windows.items()}
        parsed = parse_limits({'rateLimits': raw})
        return {'version': 1, 'updated': value['updated'], 'windows': parsed}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, MonitorError):
        return {}


def save_state(path, windows, now):
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.state-', delete=False) as stream:
            name = stream.name
            json.dump({'version': 1, 'updated': now, 'windows': windows}, stream, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
