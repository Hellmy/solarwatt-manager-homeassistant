#!/usr/bin/env bash
set -euo pipefail

workspace_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
core_dir="/workspaces/home-assistant-core"
integration_link="$core_dir/config/custom_components/solarwatt_manager"

git config --global --add safe.directory "$core_dir"
cd "$core_dir"
script/setup

mkdir -p config/custom_components
if [[ -e "$integration_link" && ! -L "$integration_link" ]]; then
  printf 'Refusing to replace existing directory: %s\n' "$integration_link" >&2
  exit 1
fi
ln -sfn "$workspace_dir/custom_components/solarwatt_manager" "$integration_link"