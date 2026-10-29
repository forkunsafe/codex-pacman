import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

MODULES = Path(__file__).resolve().parents[1] / 'plugin' / '.codex-pacman'
sys.path.insert(0, str(MODULES))
import core
import main
import rpc
import ui


def fixture(a=10, b=20):
    return {'rateLimits': {'limitId': 'codex', 'primary': {'usedPercent': a, 'windowDurationMins': 300, 'resetsAt': 2000000000}, 'secondary': {'usedPercent': b, 'windowDurationMins': 10080, 'resetsAt': 2000600000}}}


class Parsing(unittest.TestCase):
    def test_two_windows(self):
        result = core.parse_limits(fixture())
        self.assertEqual(result['primary'], {'used': 10, 'duration': 300, 'reset': 2000000000})
        self.assertEqual(result['secondary']['duration'], 10080)

    def test_optional_fields(self):
        for missing in ('primary', 'secondary'):
            value = fixture(); value['rateLimits'][missing] = None
            self.assertEqual(len(core.parse_limits(value)), 1)
        value = fixture(); del value['rateLimits']['primary']['resetsAt']
        self.assertIsNone(core.parse_limits(value)['primary']['reset'])
        del value['rateLimits']['primary']['windowDurationMins']
        self.assertIsNone(core.parse_limits(value)['primary']['duration'])

    def test_unknown_fields(self):
        value = fixture(); value['unknown'] = {'secret': 'ignored'}
        value['rateLimits']['primary']['future'] = 42
        self.assertEqual(len(core.parse_limits(value)), 2)

    def test_buckets(self):
        value = fixture()
        value['rateLimitsByLimitId'] = {'codex': fixture(33)['rateLimits'], 'other': fixture(99)['rateLimits']}
        self.assertEqual(core.parse_limits(value)['primary']['used'], 33)
        value['rateLimitsByLimitId'].pop('codex')
        with self.assertRaises(core.MonitorError): core.parse_limits(value)
        value = fixture(); value['rateLimits']['limitId'] = 'other'
        with self.assertRaises(core.MonitorError): core.parse_limits(value)

    def test_schema_errors(self):
        for value in (None, [], {}, {'rateLimits': None}, {'rateLimits': {}}, {'rateLimits': []}):
            with self.subTest(value=value), self.assertRaises(core.MonitorError): core.parse_limits(value)
        for used in (-1, 101, True, '10', float('nan'), float('inf'), 10**1000):
            value = fixture(used)
            with self.subTest(used=used), self.assertRaises(core.MonitorError): core.parse_limits(value)
        for key, invalid in [('resetsAt', 'soon'), ('resetsAt', 10**20), ('windowDurationMins', 0), ('windowDurationMins', True)]:
            value = fixture(); value['rateLimits']['primary'][key] = invalid
            with self.subTest(key=key, invalid=invalid), self.assertRaises(core.MonitorError): core.parse_limits(value)


class Animation(unittest.TestCase):
    def event(self, a, b, certain=True, gap=60):
        return core.consumed(a, b, 1000, 1000 + gap, certain)

    def test_thresholds(self):
        old = core.parse_limits(fixture(10.1, 20))
        for used, expected in [(10.9, False), (11, True), (15, True), (9, False)]:
            self.assertEqual(self.event(old, core.parse_limits(fixture(used))), expected)

    def test_simultaneous(self):
        self.assertIs(self.event(core.parse_limits(fixture()), core.parse_limits(fixture(12, 23))), True)

    def test_first_and_restart_and_uncertain(self):
        current = core.parse_limits(fixture(12, 23))
        self.assertFalse(self.event({}, current))
        self.assertFalse(self.event(core.parse_limits(fixture()), current, certain=False))
        self.assertFalse(self.event(current, current))
        self.assertFalse(self.event(core.parse_limits(fixture()), current, gap=120))
        self.assertFalse(self.event(core.parse_limits(fixture()), current, gap=-1))

    def test_reset_and_duration(self):
        old = core.parse_limits(fixture())
        for key, value in [('reset', 2000000100), ('reset', None), ('duration', 60), ('duration', None)]:
            new = core.parse_limits(fixture(12)); new['primary'][key] = value
            self.assertFalse(self.event(old, new))
        new = core.parse_limits(fixture(0, 0))
        self.assertFalse(self.event(old, new))

    def test_independent_windows(self):
        old = core.parse_limits(fixture()); new = core.parse_limits(fixture(0, 21))
        new['primary']['reset'] += 300
        self.assertTrue(self.event(old, new))

    def test_animation_and_return(self):
        windows = core.parse_limits(fixture())
        frames = [ui.render(windows, 1000, 1010, frame=f) for f in ui.animation_frames()]
        self.assertEqual(len(frames), 8)
        timing = ui.animation_frames()
        self.assertAlmostEqual(sum(f[2] for f in timing if f[1] == 'om nom nom'), 1.0)
        self.assertAlmostEqual(sum(f[2] for f in timing), 1.9)
        self.assertIn('om nom nom', frames[-1])
        normal = ui.render(windows, 1000, 1010)
        self.assertNotIn('om nom nom', normal)
        self.assertTrue(normal.startswith(' | templateImage='))
        self.assertIn(' width=16 height=16 ', normal.splitlines()[0])
        self.assertNotIn('imageWidth', normal)


class UI(unittest.TestCase):
    def test_boundaries(self):
        for remaining, label in [(100, ''), (25, ''), (24, '24%'), (10, '10%'), (9, '! 9%'), (0, '! 0%')]:
            output = ui.render(core.parse_limits(fixture(100-remaining, 0)), 1000, 1010)
            self.assertEqual(output.split(' |')[0], label)
            self.assertEqual('color=red' in output.splitlines()[0], remaining < 10)
            self.assertIn('%g%% remaining' % remaining, output)

    def test_secondary_lowest(self):
        self.assertTrue(ui.render(core.parse_limits(fixture(5, 85)), 1000, 1010).startswith('15% |'))

    def test_stale_and_error(self):
        windows = core.parse_limits(fixture())
        for now, error in [(1100, None), (1010, 'RPC timeout')]:
            result = ui.render(windows, 1000, now, error=error)
            self.assertTrue(result.startswith('! |'))
            self.assertIn('(stale)', result)
        self.assertIn('Usage unavailable', ui.render({}, 0, 1010, error='Missing login'))

    def test_sanitize(self):
        result = ui.render({}, 0, 1, name='---\n~~~\nX | bash=evil')
        self.assertNotIn('bash=evil', result.split('|')[-1])
        self.assertNotIn('~~~', result)
        self.assertNotIn('| bash=', result)
        self.assertEqual(len(result.split('---\n')[0].splitlines()), 1)
        self.assertIn('Refresh now | stdin=refresh', result)

    def test_durations(self):
        self.assertEqual(ui.title('primary', 300), '5-hour limit')
        self.assertEqual(ui.title('secondary', 10080), 'Weekly limit')
        self.assertEqual(ui.title('primary', 60), '60-minute limit')
        self.assertIn('unavailable', ui.title('primary', None))
        self.assertIn('unavailable', ui.relative(None, 1000))
        self.assertEqual(ui.relative(1000+1440*60+7*3600, 1000), 'Resets in 1d 7h')

    def test_readable_rows_and_quota_bar_colors(self):
        for used, color in [(29, ui.HEALTHY), (64, ui.MODERATE), (80, ui.WARNING), (95, ui.CRITICAL), (100, ui.CRITICAL)]:
            output = ui.render(core.parse_limits(fixture(used, used)), 1000, 1010)
            for line in output.splitlines()[2:]:
                if line != '---' and not line.startswith('Refresh now'):
                    self.assertIn('stdin=noop', line)
                    if 'font=Menlo size=11' not in line:
                        self.assertNotIn('color=', line)
            bars = [line for line in output.splitlines() if 'font=Menlo size=11' in line]
            self.assertEqual(len(bars), 2)
            self.assertTrue(all('color=' + color in line for line in bars))
            self.assertIn('Refresh now | stdin=refresh', output)
        stale = ui.render(core.parse_limits(fixture()), 1000, 1200)
        self.assertNotIn(ui.HEALTHY, stale)
        self.assertNotIn(ui.MODERATE, stale)

    def test_bar_palette_contrast_on_both_backgrounds(self):
        def luminance(color):
            channels = [int(color[i:i+2], 16)/255 for i in (1, 3, 5)]
            linear = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in channels]
            return sum(v*w for v, w in zip(linear, (.2126, .7152, .0722)))
        for foreground in (ui.HEALTHY, ui.MODERATE, ui.WARNING, ui.CRITICAL):
            self.assertNotIn(',', foreground)
            for background in ('#F5F5F5', '#252525'):
                dark, light = sorted((luminance(foreground), luminance(background)))
                self.assertGreaterEqual((light+.05)/(dark+.05), 3.0)

    def test_standard_controls_are_option_click_only(self):
        metadata = (MODULES.parent/'codex-pacman.sh').read_text()
        for field in ('hideAbout', 'hideRunInTerminal', 'hideLastUpdated', 'hideDisablePlugin', 'hideSwiftBar'):
            self.assertIn('<swiftbar.%s>true</swiftbar.%s>' % (field, field), metadata)

    def test_png(self):
        import base64
        import struct
        image = base64.b64decode(ui.icon())
        self.assertEqual(image[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(struct.unpack('!II', image[16:24]), (32, 32))


class Configuration(unittest.TestCase):
    def test_precedence_and_spaces(self):
        with tempfile.TemporaryDirectory(prefix='home with spaces ') as temporary:
            root = Path(temporary).resolve()
            for part in ('.codex', 'environment', 'explicit'):
                (root/part).mkdir()
            with patch('pathlib.Path.home', return_value=root), patch.dict(os.environ, {'HOME': str(root)}):
                self.assertEqual(core.codex_home({}), root/'.codex')
                self.assertEqual(core.codex_home({'CODEX_HOME': str(root/'environment')}), root/'environment')
                self.assertEqual(core.codex_home({'VAR_CODEX_HOME': str(root/'explicit'), 'CODEX_HOME': str(root/'environment')}), root/'explicit')
                self.assertEqual(core.codex_home({'VAR_CODEX_HOME': '~/.codex'}), root/'.codex')
                with self.assertRaises(core.MonitorError):
                    core.codex_home({'VAR_CODEX_HOME': str(root/'missing'), 'CODEX_HOME': str(root/'environment')})
                with self.assertRaises(core.MonitorError): core.codex_home({'VAR_CODEX_HOME': 'relative'})

    def test_binary_missing(self):
        with patch('shutil.which', return_value=None), patch('os.path.isfile', return_value=False):
            with self.assertRaisesRegex(core.MonitorError, 'not found'): core.executable()


class State(unittest.TestCase):
    def test_roundtrip_and_corruption(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'state.json'
            self.assertEqual(core.load_state(path), {})
            windows = core.parse_limits(fixture())
            core.save_state(path, windows, 1000)
            self.assertEqual(core.load_state(path)['windows'], windows)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(path.parent.glob('.state-*')), [])
            for text in ('bad', '[]', '{"version":1,"updated":1000,"windows":{}}', '{"version":1,"updated":1e300,"windows":{}}'):
                path.write_text(text)
                self.assertEqual(core.load_state(path), {})


class RPC(unittest.TestCase):
    def client(self, mode):
        return rpc.RPC('unused', Path('/selected home'), timeout=.15,
                       command=[sys.executable, '-u', str(Path(__file__).with_name('fake_server.py')), mode])

    def test_handshake(self):
        with self.client('ok') as client:
            process = client.process
            self.assertEqual(core.parse_limits(client.request('account/rateLimits/read'))['primary']['used'], 12)
        self.assertIsNotNone(process.poll())
        self.assertEqual(client.env['CODEX_HOME'], '/selected home')

    def test_failures_cleanup_and_redaction(self):
        for mode in ('timeout', 'malformed', 'unsupported', 'auth', 'schema', 'eof', 'huge'):
            client = self.client(mode)
            with self.subTest(mode=mode), self.assertRaises(core.MonitorError) as caught:
                with client:
                    client.request('account/rateLimits/read')
            self.assertNotIn('SECRET', str(caught.exception))
            self.assertIsNotNone(client.process.poll())

    def test_information_click_does_not_trigger_an_rpc(self):
        class Selector:
            count = 0
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def register(self, *_): pass
            def select(self, *_):
                self.count += 1
                if self.count == 1: return [object()]
                raise SystemExit()
        with tempfile.TemporaryDirectory() as temporary:
            output = io.StringIO()
            with patch.object(main, 'codex_home', return_value=Path(temporary)), patch.object(main, 'state_directory', return_value=Path(temporary)), patch.object(main, 'poll', return_value=core.parse_limits(fixture())) as poll, patch.object(main.selectors, 'DefaultSelector', Selector), patch.object(main.os, 'read', return_value=b'noop\n'), contextlib.redirect_stdout(output):
                with self.assertRaises(SystemExit): main.run()
            self.assertEqual(poll.call_count, 1)

    def test_information_click_does_not_retry_a_setup_error(self):
        class Selector:
            count = 0
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def register(self, *_): pass
            def select(self, *_):
                self.count += 1
                if self.count == 1: return [object()]
                raise SystemExit()
        output = io.StringIO()
        with patch.object(main, 'run', side_effect=[core.MonitorError('Setup unavailable'), SystemExit()]) as run, patch.object(main.selectors, 'DefaultSelector', Selector), patch.object(main.os, 'read', return_value=b'noop\n'), patch.object(main.signal, 'signal'), patch.object(main.sys, 'argv', ['main.py']), contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit): main.main()
        self.assertEqual(run.call_count, 1)

    def test_stream_loop_baseline_failure_recovery_and_single_event(self):
        with tempfile.TemporaryDirectory() as temporary:
            windows = [core.parse_limits(fixture(v)) for v in (10, 11, 11, 13, 14)]
            calls = iter([windows[0], windows[1], core.MonitorError('timeout'), windows[3], windows[4]])
            count = [0]
            def fake_poll(_):
                count[0] += 1
                if count[0] > 5: raise SystemExit()
                value = next(calls)
                if isinstance(value, Exception): raise value
                return value
            output = io.StringIO()
            class Selector:
                def __enter__(self): return self
                def __exit__(self, *_): pass
                def register(self, *_): pass
                def select(self, *_): return []
            with patch.object(main, 'codex_home', return_value=Path(temporary)), patch.object(main, 'state_directory', return_value=Path(temporary)), patch.object(main, 'poll', side_effect=fake_poll), patch.object(main.selectors, 'DefaultSelector', Selector), patch.object(main.time, 'sleep'), contextlib.redirect_stdout(output):
                with self.assertRaises(SystemExit): main.run()
            # Events 10→11 and 13→14 only; recovery 11→13 is suppressed.
            self.assertEqual(output.getvalue().count('om nom nom'), 4)
            self.assertTrue(output.getvalue().endswith('~~~\n'))
            self.assertNotIn('om nom nom', output.getvalue().split('~~~')[-2])
            self.assertEqual(core.load_state(Path(temporary)/'state.json')['windows']['primary']['used'], 14)


if __name__ == '__main__':
    unittest.main()
