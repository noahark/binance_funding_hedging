#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: install-harness.sh [--force] [--dry-run] [--source <harness_repo>] <target_project>

Install AI Project Harness into a target project for the first time.

Defaults:
  - source is the repository containing this script
  - existing target files are not overwritten unless --force is used
  - harness_owned and install_only manifest entries are copied
  - .harness-version is written unless --dry-run is used
USAGE
}

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
source_root="$(CDPATH= cd -- "$script_dir/.." && pwd)"
target_root=""
force=false
dry_run=false

while [ "$#" -gt 0 ]; do
  case "$1" in
    --force)
      force=true
      shift
      ;;
    --dry-run)
      dry_run=true
      shift
      ;;
    --source)
      source_root="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [ -n "$target_root" ]; then
        echo "Only one target project may be provided." >&2
        exit 2
      fi
      target_root="$1"
      shift
      ;;
  esac
done

if [ -z "$target_root" ]; then
  usage >&2
  exit 2
fi

source_root="$(CDPATH= cd -- "$source_root" && pwd)"
mkdir -p "$target_root"
target_root="$(CDPATH= cd -- "$target_root" && pwd)"
manifest="$source_root/harness-manifest.yaml"

if [ "$source_root" = "$target_root" ]; then
  echo "Source and target are the same directory; refusing to install." >&2
  exit 2
fi

if [ ! -f "$manifest" ]; then
  echo "Missing manifest: $manifest" >&2
  exit 1
fi

list_section() {
  local section="$1"
  awk -v section="$section" '
    $0 ~ "^[[:space:]]*" section ":" { inside=1; next }
    inside && /^[[:space:]]*[A-Za-z0-9_-]+:/ { exit }
    inside && /^[[:space:]]*-[[:space:]]*/ {
      sub(/^[[:space:]]*-[[:space:]]*/, "")
      sub(/[[:space:]]*#.*/, "")
      gsub(/^"|"$/, "")
      if (length($0) > 0) print
    }
  ' "$manifest"
}

copy_path() {
  local rel="$1"
  local src="$source_root/$rel"
  local dst="$target_root/$rel"

  if [ ! -e "${src%/}" ]; then
    echo "Missing source path: $rel" >&2
    exit 1
  fi

  if [ -e "${dst%/}" ] && [ "$force" != true ]; then
    echo "skip existing: $rel"
    return 0
  fi

  if [ "$dry_run" = true ]; then
    echo "would copy: $rel"
    return 0
  fi

  if [[ "$rel" == */ ]]; then
    mkdir -p "$dst"
    rsync -a "$src" "$dst"
  else
    mkdir -p "$(dirname -- "$dst")"
    cp "$src" "$dst"
  fi
  echo "copied: $rel"
}

write_version() {
  local commit="unknown"
  local remote="$source_root"
  if git -C "$source_root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    commit="$(git -C "$source_root" rev-parse HEAD)"
    remote="$(git -C "$source_root" config --get remote.origin.url || printf '%s' "$source_root")"
  fi

  if [ "$dry_run" = true ]; then
    echo "would write: .harness-version"
    return 0
  fi

  cat > "$target_root/.harness-version" <<VERSION
source: $remote
commit: $commit
mode: install
updated_at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
VERSION
  echo "wrote: .harness-version"
}

while IFS= read -r rel; do
  copy_path "$rel"
done < <(list_section harness_owned)

while IFS= read -r rel; do
  copy_path "$rel"
done < <(list_section install_only)

write_version

echo "Harness install complete: $target_root"
