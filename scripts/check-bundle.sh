#!/usr/bin/env bash
source "$(dirname "$0")/env.sh"
python3 - "$APP_ROOT/bundle/manifest.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1]))
if m.get('publisher_signature') or m.get('integrity',{}).get('signature'):
    raise SystemExit('Refusing to restamp a signed bundle')
PY
"$OCTO" check "$APP_ROOT/bundle"
