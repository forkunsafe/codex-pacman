#!/bin/sh
# <xbar.title>Codex Pac-Man</xbar.title>
# <xbar.version>1.0.5</xbar.version>
# <xbar.author>forkunsafe</xbar.author>
# <xbar.author.github>forkunsafe</xbar.author.github>
# <xbar.abouturl>https://github.com/forkunsafe/codex-pacman</xbar.abouturl>
# <xbar.dependencies>python3,codex</xbar.dependencies>
# <xbar.desc>A tiny SwiftBar plugin that tracks your Codex limits — and eats them.</xbar.desc>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.hideLastUpdated>true</swiftbar.hideLastUpdated>
# <swiftbar.hideDisablePlugin>true</swiftbar.hideDisablePlugin>
# <swiftbar.hideSwiftBar>false</swiftbar.hideSwiftBar>
# <swiftbar.type>streamable</swiftbar.type>
# <swiftbar.runInBash>false</swiftbar.runInBash>
# <swiftbar.useTrailingStreamSeparator>true</swiftbar.useTrailingStreamSeparator>
# <xbar.var>string(VAR_CODEX_HOME=""): Codex Home: optional directory; empty uses CODEX_HOME or ~/.codex.</xbar.var>
# <xbar.var>string(VAR_DISPLAY_NAME="Codex"): Display Name: dropdown heading only.</xbar.var>
# <xbar.var>boolean(VAR_ENABLE_ANIMATION=true): Enable Animation: pulse gold when usage increases.</xbar.var>
# GUI applications may not inherit a shell's Homebrew PATH.
for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    if [ -x "$candidate" ] && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
        exec "$candidate" -B "$(dirname "$0")/.codex-pacman/main.py" "$@"
    fi
done
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    exec python3 -B "$(dirname "$0")/.codex-pacman/main.py" "$@"
fi
printf '%s\n' '! | size=12' '---' 'Codex Pac-Man needs Python 3.9 or newer.' 'Install Python 3 from python.org or Homebrew, then refresh this plugin.' 'Refresh now | refresh=true' '~~~'
