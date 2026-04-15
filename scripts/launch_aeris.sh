#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/mnt/win_d/projects/AERIS"
AERIS_URL="http://127.0.0.1:7860"

systemctl --user start aeris.service

# Give the service a moment to bring web up, but don't block startup if it's already online.
if command -v curl >/dev/null 2>&1; then
  for _ in $(seq 1 20); do
    if curl -fsS "$AERIS_URL/health" >/dev/null 2>&1; then
      break
    fi
    sleep 0.2
  done
fi

# Open the web UI as the default interactive surface.
if command -v xdg-open >/dev/null 2>&1; then
  nohup xdg-open "$AERIS_URL" >/dev/null 2>&1 &
fi

# Ensure widget respects current hidden/show state script.
if [[ -x "$HOME/.config/eww/aeris/control.sh" ]]; then
  "$HOME/.config/eww/aeris/control.sh" show >/dev/null 2>&1 || true
fi

exit 0
