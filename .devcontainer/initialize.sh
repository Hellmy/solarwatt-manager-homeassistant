#!/usr/bin/env bash
set -euo pipefail

workspace_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
core_dir="$(dirname "$workspace_dir")/home-assistant-core"

if [[ -e "$core_dir" ]]; then
  if [[ ! -d "$core_dir/.git" || ! -f "$core_dir/Dockerfile.dev" ]]; then
    printf 'The path %s exists but is not a Home Assistant Core checkout.\n' "$core_dir" >&2
    exit 1
  fi
  exit 0
fi

git clone --depth 1 --branch dev https://github.com/home-assistant/core.git "$core_dir"