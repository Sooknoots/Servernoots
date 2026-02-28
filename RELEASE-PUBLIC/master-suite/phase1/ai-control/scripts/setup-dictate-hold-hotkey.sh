#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/media/sook/Content/Servernoots/master-suite/phase1/ai-control"
CMD_BASE="bash -lc \"cd ${ROOT_DIR} && python3 scripts/dictate-button.py\""
XBIND_FILE="${HOME}/.xbindkeysrc"

if ! command -v xbindkeys >/dev/null 2>&1; then
  echo "xbindkeys is not installed."
  echo "Install it first (Ubuntu/Debian): sudo apt update && sudo apt install -y xbindkeys"
  exit 2
fi

if command -v gsettings >/dev/null 2>&1; then
  gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/dictate/ binding '' >/dev/null 2>&1 || true
fi

if [[ ! -f "${XBIND_FILE}" ]]; then
  touch "${XBIND_FILE}"
fi

python3 - <<'PY'
from pathlib import Path
path = Path.home() / '.xbindkeysrc'
text = path.read_text(encoding='utf-8', errors='ignore') if path.exists() else ''
start = '# BEGIN SERVERNOOTS_DICTATE_HOLD\n'
end = '# END SERVERNOOTS_DICTATE_HOLD\n'
block = (
  start
  + '"bash -lc \\"cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control && python3 scripts/dictate-button.py --start\\""\n'
  + '  Mod4+Alt + z\n\n'
  + '"bash -lc \\"cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control && python3 scripts/dictate-button.py --stop\\""\n'
  + '  release+Mod4+Alt + z\n'
  + end
)
if start in text and end in text:
    pre = text.split(start, 1)[0]
    post = text.split(end, 1)[1]
    new_text = pre + block + post
else:
    if text and not text.endswith('\n'):
        text += '\n'
    new_text = text + '\n' + block
path.write_text(new_text, encoding='utf-8')
print(path)
PY

if pgrep -x xbindkeys >/dev/null 2>&1; then
  killall -HUP xbindkeys || true
else
  xbindkeys
fi

echo "HOLD_HOTKEY_READY: hold Super+Alt+Z to dictate (release to transcribe/insert)."
