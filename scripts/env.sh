#!/usr/bin/env bash
set -euo pipefail
APP_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ECO_ROOT=${ECO_ROOT:-"$(dirname "$APP_ROOT")/demo-workspace/vendor"}
DESIGN_FLOW=${DESIGN_FLOW:-"$ECO_ROOT/OctoScript-App-Design-Flow"}
export OCTOSENSE_APP_HUB=${OCTOSENSE_APP_HUB:-"$ECO_ROOT/OctoSense-App-Hub"}
export OCTO_HUB=${OCTO_HUB:-"$OCTOSENSE_APP_HUB/target/release/hub"}
export OCTO_CARD_HOST=${OCTO_CARD_HOST:-"$OCTOSENSE_APP_HUB/target/release/card-host"}
OCTO="$DESIGN_FLOW/tools/octo"
