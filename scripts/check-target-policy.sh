#!/usr/bin/env bash
source "$(dirname "$0")/env.sh"
export CARGO_TARGET_DIR="$APP_ROOT/build/policy-target"
exec cargo run --locked --manifest-path "$APP_ROOT/tests/policy-check/Cargo.toml" -- "$APP_ROOT/bundle"
