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


ICON_POINTS = 16
ICON_SCALE = 2
ICON_PIXELS = ICON_POINTS * ICON_SCALE
CORAL = (255, 90, 101)
WHITE = (255, 255, 255)


def five_hour_remaining(windows):
    """Select by actual duration, never by slot order or a different quota window."""
    candidates = [100 - window['used'] for window in windows.values() if window['duration'] == 300]
    return candidates[0] if len(candidates) == 1 else None


def fill_boundary(remaining):
    """Return the horizontal cut in Retina pixels over the unchanged silhouette."""
    if remaining is None:
        return None
    if isinstance(remaining, bool) or not isinstance(remaining, (int, float)) or not math.isfinite(remaining) or not 0 <= remaining <= 100:
        raise ValueError('Remaining quota must be a finite percentage from 0 to 100.')
    # The original 6.5-point radius spans pixels 3 through 29 on a 32px canvas.
    return 3 + 26 * remaining / 100


def rotation_components(rotation):
    """Image coordinates point down, so positive angles rotate clockwise."""
    angle = rotation % 360
    quadrants = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}
    return quadrants.get(angle) or (math.cos(math.radians(angle)), math.sin(math.radians(angle)))


@functools.lru_cache(maxsize=64)
def silhouette(open_mouth=True, rotation=0):
    """Return the original binary silhouette and its one-device-pixel inner stroke."""
    cosine, sine = rotation_components(rotation)
    mask = []
    for y in range(ICON_PIXELS):
        for x in range(ICON_PIXELS):
            dx, dy = (x + .5) / ICON_SCALE - 8, (y + .5) / ICON_SCALE - 8
            local_x, local_y = cosine*dx + sine*dy, -sine*dx + cosine*dy
            mask.append(local_x * local_x + local_y * local_y <= 42.25 and abs(math.atan2(local_y, local_x)) >= (.62 if open_mouth else .12))
    def inside(x, y):
        return 0 <= x < ICON_PIXELS and 0 <= y < ICON_PIXELS and mask[y * ICON_PIXELS + x]
    outline = tuple(mask[y * ICON_PIXELS + x] and any(not inside(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))
                    for y in range(ICON_PIXELS) for x in range(ICON_PIXELS))
    return tuple(mask), outline


def icon_pixels(remaining=None, open_mouth=True, rotation=0):
    """Clip two solid colors to the mask; never blend across the horizontal cut."""
    boundary = fill_boundary(remaining)
    mask, outline = silhouette(open_mouth, rotation % 360)
    cosine, sine = rotation_components(rotation)
    pixels = bytearray()
    for y in range(ICON_PIXELS):
        for x in range(ICON_PIXELS):
            index = y * ICON_PIXELS + x
            if not mask[index]:
                pixels.extend((0, 0, 0, 0))
            elif outline[index]:
                pixels.extend((*WHITE, 255))
            else:
                dx, dy = (x+.5)/ICON_SCALE-8, (y+.5)/ICON_SCALE-8
                local_y = (-sine*dx + cosine*dy)*ICON_SCALE + 16
                consumed = boundary is not None and local_y >= boundary
                pixels.extend((*(CORAL if consumed else WHITE), 255))
    return bytes(pixels)


def png_rgba(width, height, pixels):
    """Encode unfiltered RGBA rows with the standard library only."""
    def chunk(name, data):
        return struct.pack('!I', len(data)) + name + data + struct.pack('!I', zlib.crc32(name + data))
    stride = width * 4
    scanlines = b''.join(b'\0' + pixels[y * stride:(y + 1) * stride] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(scanlines)) + chunk(b'IEND', b''))


@functools.lru_cache(maxsize=64)
def icon(remaining=None, open_mouth=True, rotation=0):
    """Generate on demand with a bounded in-memory cache; no per-percent files."""
    return base64.b64encode(png_rgba(ICON_PIXELS, ICON_PIXELS, icon_pixels(remaining, open_mouth, rotation))).decode()


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
    icon_remaining = five_hour_remaining(windows)
    label = '!' if stale or icon_remaining is None or remaining < 10 else ''
    attrs = 'size=13 font=Menlo-Bold' if not stale and remaining < 10 else 'size=12'
    rotation = frame[0] if frame is not None else 0
    graphic = 'image=' + icon(icon_remaining, rotation=rotation)
    header = '%s | %s width=16 height=16 %s' % (label, graphic, attrs)
    lines = [header, '---', info(clean(name), 'size=13'), '---']
    if stale:
        lines.append(info('Stale data — last successful values' if windows else 'Usage unavailable', 'size=12'))
    if error:
        lines.append(info(clean(error), 'length=110 size=12'))
    if icon_remaining is None and windows:
        lines.append(info('5-hour icon quota unavailable.', 'size=11'))
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


def animation_frames():
    """One clockwise revolution in 16 fixed-size frames over two seconds."""
    return [(step*22.5, .125) for step in range(1, 17)]
