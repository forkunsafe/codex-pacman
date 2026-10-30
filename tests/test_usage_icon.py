"""Pixel-level tests for the Retina quota icon; no account access or graphics library."""
import base64
import math
from pathlib import Path
import struct
import sys
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'plugin'/'.codex-pacman'))
import ui


def decode(encoded):
    png = base64.b64decode(encoded)
    assert png[:8] == b'\x89PNG\r\n\x1a\n'
    offset, compressed = 8, b''
    while offset < len(png):
        length = struct.unpack('!I', png[offset:offset+4])[0]
        kind = png[offset+4:offset+8]
        data = png[offset+8:offset+8+length]
        if kind == b'IHDR': width, height = struct.unpack('!II', data[:8])
        if kind == b'IDAT': compressed += data
        offset += 12 + length
    raw = zlib.decompress(compressed)
    rows = []
    for y in range(height):
        start = y*(1+width*4)
        assert raw[start] == 0
        rows.extend(tuple(raw[start+1+x*4:start+5+x*4]) for x in range(width))
    return width, height, rows


class UsageIcon(unittest.TestCase):
    def test_mapping_boundaries_and_fractional_values(self):
        for remaining in (0, 1, 25, 50, 75, 99, 100, 36.75):
            with self.subTest(remaining=remaining):
                self.assertAlmostEqual(ui.fill_boundary(remaining), 3+26*remaining/100)
        self.assertIsNone(ui.fill_boundary(None))
        for bad in (-1, 101, True, '50', float('nan'), float('inf')):
            with self.subTest(bad=bad), self.assertRaises(ValueError): ui.fill_boundary(bad)

    def test_exact_clipping_cut_colors_and_outline_at_all_integer_levels(self):
        for mouth in (True, False):
            mask, outline = ui.silhouette(mouth)
            previous_count = float('inf')
            for remaining in range(101):
                _, _, pixels = decode(ui.icon(remaining, mouth))
                coral_count = 0
                for i, pixel in enumerate(pixels):
                    x, y = i % 32, i // 32
                    dx, dy = (x+.5)/2-8, (y+.5)/2-8
                    original_shape = dx*dx+dy*dy <= 42.25 and abs(math.atan2(dy,dx)) >= (.62 if mouth else .12)
                    self.assertEqual(pixel[3] != 0, original_shape)
                    if not mask[i]: self.assertEqual(pixel, (0, 0, 0, 0))
                    elif outline[i]: self.assertEqual(pixel, (*ui.WHITE, 255))
                    else:
                        color = ui.CORAL if y+.5 >= ui.fill_boundary(remaining) else ui.WHITE
                        self.assertEqual(pixel, (*color, 255))
                    coral_count += pixel == (*ui.CORAL, 255)
                self.assertLessEqual(coral_count, previous_count)
                previous_count = coral_count
        self.assertEqual(ui.icon.cache_info().maxsize, 64)

    def test_outline_is_continuous_and_includes_both_mouth_edges(self):
        for mouth in (True, False):
            mask, outline = ui.silhouette(mouth)
            border = {i for i, value in enumerate(outline) if value}
            visited, pending = set(), [next(iter(border))]
            while pending:
                i = pending.pop()
                if i in visited: continue
                visited.add(i)
                x, y = i%32, i//32
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nx, ny = x+dx, y+dy
                        j = ny*32+nx
                        if 0 <= nx < 32 and 0 <= ny < 32 and j in border and j not in visited:
                            pending.append(j)
            self.assertEqual(visited, border)
            # Internal border near the center belongs to the two mouth edges.
            self.assertTrue(any(outline[y*32+x] for y in range(10,16) for x in range(16,22)))
            self.assertTrue(any(outline[y*32+x] for y in range(16,22) for x in range(16,22)))
            _, _, exhausted = decode(ui.icon(0, mouth))
            self.assertTrue(all(exhausted[i] == (*ui.WHITE,255) for i in border))
            self.assertTrue(all(exhausted[i] == (*ui.CORAL,255) for i in range(1024) if mask[i] and not outline[i]))

    def test_full_empty_unknown_and_sharp_half_boundary(self):
        _, _, full = decode(ui.icon(100))
        _, _, unknown = decode(ui.icon(None))
        self.assertEqual(full, unknown)
        self.assertTrue(all(p[:3] == ui.WHITE for p in full if p[3]))
        _, _, half = decode(ui.icon(50))
        mask, outline = ui.silhouette()
        for i, p in enumerate(half):
            if not mask[i] or outline[i]: continue
            self.assertEqual(p[:3], ui.WHITE if i//32 < 16 else ui.CORAL)
        self.assertEqual({p[3] for p in half}, {0,255})

    def test_clockwise_quarter_turns_rotate_the_complete_bitmap(self):
        for remaining in (0,1,25,50,75,99,100,None):
            _,_,base = decode(ui.icon(remaining))
            for angle, source_point in [(90,lambda x,y:(y,31-x)), (180,lambda x,y:(31-x,31-y)), (270,lambda x,y:(31-y,x))]:
                _,_,rotated = decode(ui.icon(remaining,rotation=angle))
                expected = [base[sy*32+sx] for y in range(32) for x in range(32) for sx,sy in [source_point(x,y)]]
                self.assertEqual(rotated,expected)
            self.assertEqual(ui.icon(remaining,rotation=360),ui.icon(remaining))

    def test_every_rotation_preserves_white_outline_and_attached_fill(self):
        for remaining in (0,25,50,75,100):
            for angle,_ in ui.animation_frames():
                mask,outline = ui.silhouette(rotation=angle%360)
                _,_,pixels = decode(ui.icon(remaining,rotation=angle))
                cosine,sine = ui.rotation_components(angle)
                border = {i for i,value in enumerate(outline) if value}
                visited,pending = set(),[next(iter(border))]
                while pending:
                    i=pending.pop()
                    if i in visited: continue
                    visited.add(i)
                    x,y=i%32,i//32
                    for dx in (-1,0,1):
                        for dy in (-1,0,1):
                            nx,ny=x+dx,y+dy
                            if 0<=nx<32 and 0<=ny<32 and ny*32+nx in border and ny*32+nx not in visited:
                                pending.append(ny*32+nx)
                self.assertEqual(visited,border)
                for i,pixel in enumerate(pixels):
                    if not mask[i]: self.assertEqual(pixel,(0,0,0,0))
                    elif outline[i]: self.assertEqual(pixel,(*ui.WHITE,255))
                    else:
                        x,y=i%32,i//32
                        local_y=(-sine*((x+.5)/2-8)+cosine*((y+.5)/2-8))*2+16
                        expected=ui.CORAL if local_y>=ui.fill_boundary(remaining) else ui.WHITE
                        self.assertEqual(pixel,(*expected,255))
                self.assertEqual({p[3] for p in pixels},{0,255})

    def test_uses_duration_not_slot_and_does_not_mix_weekly_usage(self):
        windows = {'primary': {'used':99,'duration':10080,'reset':2000000000},
                   'secondary': {'used':25,'duration':300,'reset':2000000000}}
        self.assertEqual(ui.five_hour_remaining(windows), 75)
        first = ui.render(windows,1000,1010).splitlines()[0]
        windows['primary']['used'] = 10
        second = ui.render(windows,1000,1010).splitlines()[0]
        self.assertEqual(first.split('image=')[1].split()[0], second.split('image=')[1].split()[0])
        del windows['secondary']
        unknown = ui.render(windows,1000,1010)
        self.assertTrue(unknown.startswith('! | image='))
        self.assertIn('5-hour icon quota unavailable.',unknown)
        self.assertIsNone(ui.five_hour_remaining(windows))
        windows['secondary']={'used':25,'duration':None,'reset':None}
        self.assertIsNone(ui.five_hour_remaining(windows))
        windows['primary']['duration']=300;windows['secondary']['duration']=300
        self.assertIsNone(ui.five_hour_remaining(windows))

    def test_reset_changes_icon_and_unchanged_usage_reuses_png(self):
        windows = {'primary': {'used':75,'duration':300,'reset':2000000000}}
        old = ui.render(windows,1000,1010).splitlines()[0]
        self.assertEqual(old,ui.render(windows,1010,1020).splitlines()[0])
        windows['primary'].update(used=0,reset=2000018000)
        self.assertNotEqual(old,ui.render(windows,1020,1030).splitlines()[0])
        self.assertEqual(decode(ui.icon(25))[:2],(32,32))


if __name__ == '__main__':
    unittest.main()
