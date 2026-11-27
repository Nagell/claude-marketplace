#!/usr/bin/env bash
# Runs the pinned Playwright CLI against Playwright's own Chrome for Testing.
# Use it for every CLI call once a session is up:
#
#   pw.sh -s=<session> goto https://example.com
#   pw.sh -s=<session> run-code --filename script.js
#
# It never downloads anything: when the pinned CLI is not on disk it fails,
# and `launch.sh --allow-install` fetches it after the user has agreed.
set -euo pipefail

# shellcheck source-path=SCRIPTDIR source=common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# `chromium` selects Chrome for Testing and has no `--browser` value, so the env
# var is the handle. npm and not npx: where Volta manages Node its npx shim
# forwards the arguments to npm and dies on `Unknown command`.
PLAYWRIGHT_MCP_BROWSER=chromium exec npm exec --no -- "$PW_CLI_PKG" "$@"
