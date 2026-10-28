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

## Limits of verification

No real quota was intentionally exhausted or reset. Warning/exhausted rendering, uncertain recovery, first-start/restart suppression, malformed state, and RPC errors are covered by automated tests. Physical sleep/wake, Intel hardware, older Python versions, older Codex versions, missing-Python UI, long-duration use, and both macOS appearances have not been exercised end to end. Color readability is reinforced by a textual warning and native template imagery, but appearance-specific visual verification remains outstanding.

The README image is a synthetic SVG illustration, not a captured screenshot. No private screen capture or account fixture is distributed.
