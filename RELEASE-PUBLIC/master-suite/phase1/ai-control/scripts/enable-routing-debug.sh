#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

WORKFLOW_FILE="workflows/rag-query-webhook.json"
WORKFLOW_ID="e2f4c63a-6ac9-46ce-9ee4-39d1d8de9128"

if [[ ! -f "$WORKFLOW_FILE" ]]; then
  echo "[FAIL] Missing $WORKFLOW_FILE"
  exit 1
fi

python3 - <<'PY' "$WORKFLOW_FILE"
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text(encoding='utf-8'))
workflow = data[0]
changed = 0

for node in workflow.get('nodes', []):
    node_id = node.get('id')
    if node_id in {'format_rag_reply', 'format_general_reply'}:
        params = node.setdefault('parameters', {})
        js = params.get('jsCode', '')
        if 'const debugEnabled = false;' in js:
            params['jsCode'] = js.replace('const debugEnabled = false;', 'const debugEnabled = true;')
            changed += 1

path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
print(f"UPDATED_NODES={changed}")
PY

python3 -m json.tool "$WORKFLOW_FILE" >/tmp/rag-query-after-enable-debug.json

docker exec n8n n8n import:workflow --input=/opt/workflows/rag-query-webhook.json
docker exec n8n n8n publish:workflow --id="$WORKFLOW_ID"
docker compose restart n8n >/dev/null
sleep 4

echo "[OK] Routing debug markers enabled and workflow redeployed."
