# Codex Pac-Man

**A tiny SwiftBar plugin that tracks your Codex limits — and eats them.**

A monochrome Pac-Man stays quietly in your menu bar. Click it for your remaining Codex quota and reset times. When you consume another whole percentage point, Pac-Man briefly eats dots and says **om nom nom**.

Codex Pac-Man is an independent community project. It is not affiliated with, endorsed by, or sponsored by OpenAI. Codex and Pac-Man names belong to their respective owners. The small geometric icon is drawn by this project; no game artwork or sounds are included.

![Illustrative interface with synthetic values](docs/preview.svg)

*Illustration with synthetic values, not a screenshot.*

## Requirements

- macOS with **SwiftBar 2.1.1 or newer**. SwiftBar provides the menu bar item, native settings, images, and streaming updates; this plugin is not another menu bar app.
- **Python 3.9+**, standard library only. Homebrew Python and python.org Python work. The launcher checks common Homebrew locations on Apple Silicon and Intel, `/usr/bin/python3`, then inherited `PATH`.
- Codex CLI with `app-server` and `account/rateLimits/read`, authenticated normally using a quota-bearing account. Verified locally against **Codex CLI 0.165.0**, SwiftBar **2.1.1 (597)**, Python **3.15**, and macOS **27.0.1** on Apple Silicon. Earlier Codex releases and Intel hardware have not been tested.
- ChatGPT-backed Codex quotas. API-key billing, model-specific buckets, credits, spend controls, and purchased balances are not combined with ordinary Codex quota.

The app-server protocol can change with Codex upgrades. Unknown optional fields are ignored; incompatible structures produce a visible error rather than invented percentages.

## Install

1. Install Codex CLI, authenticate normally (`codex login`), and install SwiftBar. With Homebrew:

   ```sh
   brew install --cask codex swiftbar
   brew install python
   codex login
   ```

2. Open SwiftBar and select its Plugin Folder if this is your first launch.
3. Download or clone this repository, then run from its root:

   ```sh
   python3 install.py
   ```

The installer discovers the existing SwiftBar Plugin Folder from SwiftBar preferences. To choose it explicitly:

```sh
python3 install.py --plugin-dir "$HOME/My SwiftBar Plugins"
```

No administrator privileges are needed. Only `codex-pacman.sh` and its hidden `.codex-pacman` module directory are installed. Other plugins are preserved. SwiftBar normally discovers the new plugin immediately. If needed, use SwiftBar's Reload Plugins action.

Manual installation: copy **both** `plugin/codex-pacman.sh` and `plugin/.codex-pacman` to your Plugin Folder; keep the hidden directory. Make the launcher executable with `chmod +x`. A source archive is already a complete distribution; no build or dependency installation is necessary. Maintainers can produce a filtered distribution with `python3 tools/package.py`; the archive is written to `dist/` and excludes Git metadata, settings, state, and bytecode.

## Configure

Open **SwiftBar → Settings → Plugins → Codex Pac-Man**. The plugin declares three native `xbar.var` variables:

| Setting | Default | Meaning |
| --- | --- | --- |
| Codex Home | Empty | Select one Codex environment; absolute paths, `~`, and spaces are supported. |
| Display Name | `Codex` | Heading in the dropdown only. |
| Enable Animation | Enabled | Disable to show quota without consumption animations. |

Codex Home is resolved in this exact order:

1. Nonempty **Codex Home** native setting (`VAR_CODEX_HOME`).
2. Inherited `CODEX_HOME`.
3. `~/.codex`.

An invalid selected path is an error. The plugin never scans for profiles or silently falls back to another account. Relative paths are rejected. GUI applications may not inherit your terminal environment; use the native setting for custom profiles. Only one selected environment is monitored per plugin instance.

You can also set the native value at installation, without opening or reading the selected account:

```sh
python3 install.py --codex-home "$HOME/My Personal Codex"
```

SwiftBar stores its native values beside the launcher in `codex-pacman.vars.json`. This is SwiftBar's own configuration mechanism, not a separate settings system. It may sync if your Plugin Folder syncs. Do not commit that file or distribute it with a release. After editing settings, refresh only this plugin if SwiftBar has not restarted it automatically.

## Display and animation

- Normal: a 16-point monochrome template icon (a 32×32 retina raster), with no percentage or text label. macOS supplies native status-item padding and appearance adaptation.
- Below **25%** remaining: the lowest remaining percentage across available windows.
- Below **10%**: a compact `!` plus the percentage in red. The textual warning remains visible regardless of color/appearance.
- Exhausted: `! 0%`.
- Error or stale data: compact `!`, with details in the dropdown. Cached values are explicitly marked stale.

The dropdown shows both windows when available, actual durations from the server (commonly 5 hours and one week), remaining percentages, ten-cell bars, relative reset times, absolute times in the local timezone, and the last successful update. A missing window, duration, or reset timestamp is identified without assuming a 5-hour/weekly mapping.

Consumption in either window can trigger one **1.6-second animation** (eight 200 ms frames), even if several percent were consumed between polls. Pac-Man opens/closes its mouth, dots disappear, and `om nom nom` briefly appears. It then returns to the normal or warning display. There is no sound or notification.

Only consecutive, trustworthy observations of the same window duration and reset timestamp are compared. First startup, process restart, errors, backwards clocks, gaps over 90 seconds, missing reset metadata, usage decreases, and quota resets establish a baseline without animating the affected change. Each window is tracked independently. State is committed before animation, so an interrupted animation is never replayed. This deliberately favors missing an animation over showing a misleading one.

## Refresh and errors

Quota is polled roughly every **60 seconds after the previous request finishes**. Use **Refresh now** for an immediate serialized request via SwiftBar's native `stdin` action. Rapid clicks are coalesced with a two-second minimum request spacing. No overlapping RPC calls are made.

There is no filesystem scan, session-log parsing, thread creation, model request, or manual credential extraction. The plugin does not initiate login or call authentication-changing RPCs. Codex itself consumes its selected environment's normal authentication; the plugin never opens credential files or copies tokens. Server error messages and stderr are not displayed or logged because they may contain sensitive information. No data is sent to third-party services. Codex analytics and telemetry export are disabled for the child process.

- **CLI not found:** install Codex CLI. The plugin checks inherited `PATH`, `/opt/homebrew/bin/codex`, and `/usr/local/bin/codex`, without scanning disks. Restart/refresh this plugin after installation.
- **Home missing:** correct Codex Home in native settings. No alternate account will be used.
- **Authentication/quota unavailable:** run Codex normally with the *same selected* `CODEX_HOME`, and authenticate there yourself if necessary. For a custom home, use `CODEX_HOME="$HOME/My Personal Codex" codex login`. API-key-only accounts may have no ChatGPT quota.
- **RPC unsupported, timeout, or changed response:** update Codex CLI and the plugin. Automatic retries continue; existing successful values remain clearly stale. No raw RPC diagnostics or credentials are retained.
- **Python missing:** the launcher shows installation instructions. Install Python 3.9+ and refresh the plugin.
- **After sleep/wake:** the next scheduled or manual request refreshes usage. A long gap suppresses animation. There is no wake observer or background service; wake recovery may take approximately one polling interval plus the request timeout.
- **Corrupt state:** it is discarded and the next success establishes a baseline. If needed, remove the private state directory below while the plugin is disabled.
- **Another instance stopping:** the lifetime lock prevents overlap; retry occurs automatically or via Refresh now. Use a plugin-specific refresh, not a refresh of all your other plugins.

For a one-shot diagnostic through the real implementation (it uses the resolved environment and saves minimal state):

```sh
VAR_CODEX_HOME="$HOME/My Personal Codex" plugin/codex-pacman.sh --once
```

It prints SwiftBar markup, not credentials. A running instance prevents a concurrent diagnostic with the same plugin identity/environment.

## Architecture and resource use

Four small standard-library modules handle quota/configuration/state, bounded stdio RPC, rendering, and the streaming event loop. A POSIX launcher finds a suitable Python without relying on interactive shell setup.

Each poll starts `codex app-server`, sends `initialize` with stable client metadata, waits for its response, sends `initialized`, and requests **`account/rateLimits/read`**. Requests are newline-delimited JSON without a JSON-RPC version member, matching the installed protocol. Only the `codex` bucket is selected from `rateLimitsByLimitId`; the legacy `rateLimits` field is used only when the map is absent. Remaining quota is `100 - usedPercent`; duration and reset metadata are read directly. Raw responses, account IDs, and credit information are discarded.

A persistent Python process emits complete SwiftBar frames terminated by `~~~`. It sleeps in a selector between polls, and uses `time.sleep` during animation. The short-lived Codex child is closed gracefully after each request, with bounded termination of this owned child if it will not exit. SIGTERM/SIGINT and broken output pipes are handled. There are no threads, servers, LaunchAgents, or extra menu bar items. A lifetime file lock prevents overlapping instances; requests have a 15-second timeout and a 1 MiB buffer cap.

**Why not persistent app-server?** The installed server measured about **136 MiB RSS** during a simple quota request; a successful probe finished in under a second. Keeping that process alive all day would avoid one launch per minute but retain substantially more idle memory. Short-lived requests use more process startups but release server memory immediately, recover naturally after Codex upgrades, and isolate request failures. Animation never starts additional Codex processes.

In an observed installed idle process, Python used about **23 MiB RSS**, showed **0.0% CPU** in a process snapshot, and accumulated **0.04 CPU seconds over approximately 94 seconds**. These are observations from one machine, not guarantees or a long-duration benchmark.

Minimal local state is stored under:

```text
~/Library/Application Support/Codex Pac-Man/<plugin-identity-hash>/<home-hash>/
```

Only window usage, durations, reset timestamps, last successful update, a schema version, and an empty lock file are retained. Identity paths are hashed rather than stored in state. State writes use private temporary files, fsync, and atomic replacement. A new process always suppresses its first animation. State is separate from code and SwiftBar settings.

**Packaging limitation:** SwiftBar 2.1.1 explicitly ignores streaming metadata in `.swiftbar` packages. A normal streaming launcher plus a hidden support directory supports both native variables and animation. The support directory is hidden so SwiftBar does not import each module as a plugin. Future package-streaming support can simplify distribution without changing the quota logic.

## Update and uninstall

Disable **only Codex Pac-Man** from its menu before updating or uninstalling, so the process can exit cleanly.

```sh
python3 install.py --update
```

Updates replace only plugin code and preserve native settings. Then re-enable this plugin in SwiftBar.

To uninstall, run from this repository:

```sh
python3 install.py --uninstall
```

Use the same `--plugin-dir` if you supplied one during installation. This removes only `codex-pacman.sh`, `.codex-pacman`, `codex-pacman.vars.json`, and state for that plugin identity (including previously selected homes). Codex authentication, installation, and other SwiftBar plugins are untouched. The empty top-level state directory and SwiftBar-managed cache/metadata may remain.

Manual uninstall: disable this plugin, delete those three entries from your Plugin Folder, then remove `~/Library/Application Support/Codex Pac-Man` if you have no other instances. No Codex files should be deleted.

## Tests and verification

```sh
python3 -B -m unittest discover -s tests -v
```

Tests use synthetic fixtures and a real mocked subprocess, without contacting Codex or reading account data. Coverage includes initialization and notification handling, both quota windows and optional metadata, bucket isolation, malformed/unsupported/oversized RPC, timeout/EOF cleanup, percentage boundaries, independent windows, resets, baseline/restart/recovery suppression, one animation per event, return to normal, stale/error output, template PNG shape, markup sanitation, configuration precedence, spaces, no account fallback, atomic/corrupt state, and installation/update/uninstallation preserving other plugins.

See [verification notes](docs/verification.md) for the exact scope of live checks and unverified behavior. No unit test is a claim of visual macOS compatibility.

Protocol references: [Codex app-server](https://developers.openai.com/codex/app-server), [SwiftBar documentation](https://github.com/swiftbar/SwiftBar#readme), and [SwiftBar 2.1.1 source](https://github.com/swiftbar/SwiftBar/tree/v2.1.1). The installed Codex CLI's `app-server generate-json-schema` output was used to check request and response types. MIT licensed; see [LICENSE](LICENSE).
