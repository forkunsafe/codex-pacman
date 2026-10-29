# Verification scope

## Live environment

Verified with Codex CLI 0.165.0 (Homebrew), SwiftBar 2.1.1 build 597, Python 3.15.2, macOS 27.0.1, and Apple Silicon.

The configured Codex home was confirmed before starting authenticated requests. No other Codex home was scanned or accessed. Machine-specific settings and quota state are not included in this repository.

- Generated JSON Schema from the installed CLI to verify the initialize request, empty rate-limit request, optional metadata, legacy view, and multi-bucket response.
- Successfully initialized the real app-server, sent `initialized`, and received primary (300-minute) and secondary (10080-minute) windows from `account/rateLimits/read`.
- Installed into an existing SwiftBar Plugin Folder containing other plugins. Only the new plugin and its own native variable settings were added.
- Observed exactly one additional status item and one Python streaming process parented by SwiftBar.
- Opened the real dropdown through macOS Accessibility. Read both limit labels, percentages, progress bars, relative/absolute reset timestamps in local time, and last successful update.
- Clicked the plugin's real `Refresh now` menu action, then checked the state timestamp and quota update.
- Observed a real usage increase with the initial animation timing through macOS Accessibility sampling every 200 ms: the installed status item showed `· · ·`, `· ·`, `·`, and `om nom nom`, then returned to an empty title with its template icon. The animation was not driven by synthetic quota or extra Codex requests. Final timing was subsequently changed to a 1.9-second total with a one-second message hold; that timing is covered by automated assertions.
- Verified image sizing with SwiftBar's `width=16 height=16` parameters. Accessibility reported the idle status-item width decreasing from 38 points to 22 points including native padding. The PNG remains 32×32 for retina display. A cropped screen-capture attempt was unavailable; the revised visual appearance has not been independently screen-captured.
- Confirmed the native Codex Home variable selected the configured Codex home.
- Observed idle Python at approximately 23 MiB RSS, 0.0% CPU in a snapshot, and 0.04 CPU seconds after approximately 94 seconds. The live Codex RPC probe used approximately 136 MiB RSS and completed in under a second. No continuous profiling or battery benchmark was performed.

SwiftBar source was checked at tag `v2.1.1` (`05cb6cb1123bc7227ee2b39f390f8bccb839fed0`): native `xbar.var` storage/injection, stdin actions, trailing `~~~` separators, template images, and explicit exclusion of streaming support in `.swiftbar` packages. This is why distribution uses a normal streaming launcher and hidden support modules.

## Automated checks

Run `python3 -B -m unittest discover -s tests -v`. Fixtures are synthetic; RPC tests launch a small mock subprocess. See README for coverage. Installer tests use a temporary folder containing another plugin, preserve that plugin, preserve native settings on update, and remove only this plugin and its private state on uninstall. The shell launcher is checked with `sh -n`.

## Homebrew packaging

Version 1.0.1 adds the `codex-pacman` command and link-based installation for Homebrew. The automated suite contains 29 tests, including migration from a copied installation while retaining settings, stable links following a simulated Homebrew opt switch, and rollback after a failed module swap. These simulations are separate from the following real Homebrew checks, which also passed locally:

- `brew install forkunsafe/tap/codex-pacman` fetched the public tap and installed the public 1.0.1 release with checksum verification.
- `brew test forkunsafe/tap/codex-pacman` exercised the installed command, linked installation into a temporary SwiftBar folder, and uninstalled those links while preserving another fixture plugin and the packaged source.
- `brew audit --strict forkunsafe/tap/codex-pacman` completed successfully for the final formula.
- The existing live SwiftBar installation was migrated with `codex-pacman install --update`. Both code entries pointed to the stable Homebrew opt path, native settings were byte-for-byte unchanged, neighboring plugin files retained their checksums, and the restarted stream produced fresh quota state for both windows.
- The Homebrew formula inventory added only `codex-pacman 1.0.1`; existing formula versions were unchanged. Homebrew's standard test/audit tooling populated its own Ruby vendor cache. No runtime Python packages or background services were added by the project.

Intel Homebrew installation has not been exercised. A real 1.0.1-to-1.0.2 upgrade subsequently passed; launcher metadata required reconnecting as described below. Upgrade-link behavior is covered by the opt-switch subprocess test.

## Readable dropdown (1.0.2)

The 31-test suite checks explicit light/dark color pairs on informational rows, quota-dependent bar colors, muted stale data, an unchanged active refresh action, and metadata hiding standard controls. SwiftBar 2.1.1 source confirms that supplying a color also enables informational menu items, preventing disabled grey rendering, and that Option-click reveals hidden standard items. The real 1.0.1-to-1.0.2 Homebrew upgrade, formula test, and strict audit passed. Accessibility confirmed enabled informational rows and hidden standard controls after reconnecting the launcher. SwiftBar cached launcher metadata across the opt switch; the update instructions now require `codex-pacman install --update` while only this plugin is disabled, followed by re-enabling it. Option-click reveal is confirmed by SwiftBar source and documentation; synthetic input did not establish an end-to-end reveal, so it is not claimed as a live check. The palette's minimum calculated contrast against representative solid backgrounds (`#F5F5F5` and `#252525`) is 5.22:1; this is not a measurement of translucent macOS menu backgrounds or a claim of visual testing in both themes.

## Native system text (1.0.3)

Version 1.0.2's fixed text colors could remain cached during a system appearance change, producing a mixture of light- and dark-theme text. Version 1.0.3 supersedes that approach: informational rows omit `color=` and use a harmless `stdin=noop` action so SwiftBar renders them enabled with AppKit's adaptive `controlTextColor`. Only quota graphics and the critical menu bar warning use explicit accents. Graphical accents use one appearance-independent palette, with a minimum 3.55:1 calculated contrast against representative solid backgrounds (`#F5F5F5` and `#252525`). This does not guarantee the contrast of every translucent menu background.

All 33 Python tests passed, including native-text markup, bar-color boundaries, stale rendering, and an event-loop check that informational clicks do not trigger another RPC. The optional native AppKit check (`swift tools/check-native-colors.swift`) retained the same attributed text and resolved its stored system foreground color as black, white, and black under Aqua → Dark Aqua → Aqua. This confirms adaptive color resolution without rebuilding the text or changing global system appearance. It is separate from an end-to-end screen test of the entire plugin in both system themes.

## Limits of verification

No real quota was intentionally exhausted or reset. Warning/exhausted rendering, uncertain recovery, first-start/restart suppression, malformed state, and RPC errors are covered by automated tests. Physical sleep/wake, Intel hardware, older Python versions, older Codex versions, missing-Python UI, long-duration use, and both macOS appearances have not been exercised end to end. Color readability is reinforced by a textual warning and native template imagery, but appearance-specific visual verification remains outstanding.

The README image is a synthetic SVG illustration, not a captured screenshot. No private screen capture or account fixture is distributed.
