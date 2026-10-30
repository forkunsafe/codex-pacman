"""Native template images and injection-safe SwiftBar output."""
import base64
from datetime import datetime
import functools
import math
import struct
import zlib

# Accents are graphics, not body text: each remains distinguishable on both
# light and dark menu backgrounds, so no theme detection or recoloring is needed.
HEALTHY = '#338A52'
MODERATE = '#337FB8'
WARNING = '#A47620'
CRITICAL = '#C45A58'


def info(text, attributes=''):
    # A harmless stdin action keeps AppKit's adaptive controlTextColor enabled.
    # The stream ignores noop; reading/clicking information never polls Codex.
    return (str(text) + ' | stdin=noop ' + attributes).rstrip()


def quota_color(remaining):
    if remaining < 10:
        return CRITICAL
    if remaining < 25:
        return WARNING
    if remaining < 50:
        return MODERATE
    return HEALTHY


def clean(text):
    # A label must never become a SwiftBar command, separator, or submenu.
    value = ''.join(c if c.isprintable() else ' ' for c in str(text)).replace('|', '¦').replace('~~~', '≈')
    return value.strip().lstrip('-')[:180] or 'Codex'


@functools.lru_cache(maxsize=6)
def icon(open_mouth=True, gold=False, dark=False):
    width, height, scale = 16, 16, 2
    rgb = ((255, 211, 58) if dark else (174, 115, 0)) if gold else (0, 0, 0)
    w, h = width * scale, height * scale
    pixels = bytearray()
    for y in range(h):
        pixels.append(0)
        for x in range(w):
            dx, dy = (x + .5) / scale - 8, (y + .5) / scale - 8
            inside = dx * dx + dy * dy <= 42.25
            mouth = abs(math.atan2(dy, dx)) < (.62 if open_mouth else .12)
            filled = inside and not mouth
            pixels.extend((*rgb, 255 if filled else 0))
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
    mouth = frame[0] if frame else True
    if frame is not None and frame[1]:
        graphic = 'image=' + icon(mouth, gold=True) + ',' + icon(mouth, gold=True, dark=True)
    else:
        graphic = 'templateImage=' + icon(mouth)
    header = '%s | %s width=16 height=16 %s' % (label, graphic, attrs)
    lines = [header, '---', info(clean(name), 'size=13'), '---']
    if stale:
        lines.append(info('Stale data — last successful values' if windows else 'Usage unavailable', 'size=12'))
    if error:
        lines.append(info(clean(error), 'length=110 size=12'))
    for slot, window in windows.items():
        pct = 100 - window['used']
        bars = max(0, min(10, int(pct / 10 + .5)))
        bar_attributes = 'font=Menlo size=11'
        if not stale:
            bar_attributes += ' color=' + quota_color(pct)
        lines += [info(title(slot, window['duration']), 'size=12'),
                  info('  %g%% remaining%s' % (pct, ' (stale)' if stale else ''), 'font=Menlo-Bold size=13'),
                  info('  ' + '█' * bars + '░' * (10 - bars), bar_attributes),
                  info('  ' + relative(window['reset'], now), 'size=12')]
        if window['reset'] is not None:
            try:
                lines.append(info('  ' + datetime.fromtimestamp(window['reset']).astimezone().strftime('%a %d %b %H:%M %Z'), 'size=11'))
            except (ValueError, OSError, OverflowError):
                pass
    if len(windows) == 1:
        lines.append(info('Only one quota window is available.', 'size=11'))
    lines += ['---', info('Last successful update: ' + (datetime.fromtimestamp(updated).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z') if updated else 'never'), 'size=11'),
              'Refresh now | stdin=refresh', 'Preview animation | stdin=preview']
    return '\n'.join(lines) + '\n'


GOLD_SECONDS = 12
GOLD_FRAME = (True, True, 0)


def animation_frames():
    """Two compact gold pulses; the event loop manages the idle gold afterglow."""
    return [(False, True, .2), (True, False, .15), (True, True, .25),
            (False, True, .2), (True, False, .15), (True, True, .25)]
