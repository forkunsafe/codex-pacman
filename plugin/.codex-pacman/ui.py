"""Native template images and injection-safe SwiftBar output."""
import base64
from datetime import datetime
import functools
import math
import struct
import zlib


def clean(text):
    # A label must never become a SwiftBar command, separator, or submenu.
    value = ''.join(c if c.isprintable() else ' ' for c in str(text)).replace('|', '¦').replace('~~~', '≈')
    return value.strip().lstrip('-')[:180] or 'Codex'


@functools.lru_cache(maxsize=3)
def icon(open_mouth=True, dots=False):
    width, height, scale = (44 if dots else 16), 16, 2
    w, h = width * scale, height * scale
    pixels = bytearray()
    for y in range(h):
        pixels.append(0)
        for x in range(w):
            dx, dy = (x + .5) / scale - 8, (y + .5) / scale - 8
            inside = dx * dx + dy * dy <= 42.25
            mouth = abs(math.atan2(dy, dx)) < (.62 if open_mouth else .12)
            filled = inside and not mouth
            if dots:
                filled |= any(((x + .5) / scale - cx) ** 2 + dy ** 2 <= 1 for cx in (23, 31, 39))
            pixels.extend((0, 0, 0, 255 if filled else 0))
    def chunk(name, data):
        return struct.pack('!I', len(data)) + name + data + struct.pack('!I', zlib.crc32(name + data))
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', w, h, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(bytes(pixels))) + chunk(b'IEND', b'')
    return base64.b64encode(png).decode()


def relative(reset, now):
    if reset is None:
        return 'Reset time unavailable'
    seconds = max(0, int(reset - now))
    if seconds == 0:
        return 'Reset due; awaiting refreshed quota'
    minutes = (seconds + 59) // 60
    if minutes >= 1440:
        return 'Resets in %dd %dh' % (minutes // 1440, minutes % 1440 // 60)
    return 'Resets in %dh %dm' % (minutes // 60, minutes % 60)


def title(slot, duration):
    if duration == 300:
        return '5-hour limit'
    if duration == 10080:
        return 'Weekly limit'
    if duration is None:
        return slot.capitalize() + ' limit (duration unavailable)'
    return '%g-minute limit' % duration


def render(windows, updated, now, name='Codex', error=None, frame=None):
    stale = bool(error) or not updated or not 0 <= now - updated <= 90
    remaining = min((100 - w['used'] for w in windows.values()), default=100)
    label = ''
    attrs = 'size=12'
    if remaining < 25:
        # Round down so a partially exhausted percent never looks safer.
        label = '%d%%' % math.floor(remaining)
    if remaining < 10:
        label = '! ' + label
        attrs += ' color=red'
    if stale:
        label = '!'
        attrs = 'size=12'
    if frame is not None:
        label = frame[1]
    image = icon(frame[0] if frame else True)
    header = '%s | templateImage=%s width=16 height=16 %s' % (label, image, attrs)
    lines = [header, '---', clean(name), '---']
    if stale:
        lines.append('Stale data — last successful values' if windows else 'Usage unavailable')
    if error:
        lines.append(clean(error) + ' | length=110')
    for slot, window in windows.items():
        pct = 100 - window['used']
        bars = max(0, min(10, int(pct / 10 + .5)))
        lines += [title(slot, window['duration']), '  %g%% remaining%s' % (pct, ' (stale)' if stale else ''),
                  '  ' + '█' * bars + '░' * (10 - bars) + ' | font=Menlo size=10',
                  '  ' + relative(window['reset'], now)]
        if window['reset'] is not None:
            try:
                lines.append('  ' + datetime.fromtimestamp(window['reset']).astimezone().strftime('%a %d %b %H:%M %Z'))
            except (ValueError, OSError, OverflowError):
                pass
    if len(windows) == 1:
        lines.append('Only one quota window is available.')
    lines += ['---', 'Last successful update: ' + (datetime.fromtimestamp(updated).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z') if updated else 'never'),
              'Refresh now | stdin=refresh', 'Settings: SwiftBar → Settings → Plugins → Codex Pac-Man']
    return '\n'.join(lines) + '\n'


def animation_frames():
    """Eat dots at 150 ms per frame; keep the final message visible for one second."""
    return [(True, '· · ·', .15), (False, '· · ·', .15),
            (True, '· ·', .15), (False, '· ·', .15),
            (True, '·', .15), (False, '·', .15),
            (True, 'om nom nom', .5), (False, 'om nom nom', .5)]
