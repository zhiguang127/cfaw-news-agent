#!/usr/bin/env bash
source "$(dirname "$0")/env.sh"
python3 - "$APP_ROOT/bundle/manifest.json" <<'CHECK'
import json,sys
if json.load(open(sys.argv[1])).get('integrity',{}).get('signature'):
    raise SystemExit('Refusing to restamp a signed bundle')
CHECK
exec "$OCTO" run "$APP_ROOT/bundle" "$@"
