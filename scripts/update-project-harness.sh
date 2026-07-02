#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: update-project-harness.sh [--allow-dirty] [--dry-run] [--source <harness_repo>] [target_project]

Update Harness-owned files in an existing target project.

Defaults:
  - source is the repository containing this script
  - target_project is the current directory
  - only harness_owned manifest entries are copied
  - install_only/project-owned docs are never overwritten
  - dirty target git worktrees are rejected unless --allow-dirty is used
USAGE
}

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
source_root="$(CDPATH= cd -- "$script_dir/.." && pwd)"
target_root="."
allow_dirty=false
dry_run=false

while [ "$#" -gt 0 ]; do
  case "$1" in
    --allow-dirty)
      allow_dirty=true
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
      target_root="$1"
      shift
      ;;
  esac
done

source_root="$(CDPATH= cd -- "$source_root" && pwd)"
target_root="$(CDPATH= cd -- "$target_root" && pwd)"
manifest="$source_root/harness-manifest.yaml"

if [ "$source_root" = "$target_root" ]; then
  echo "Source and target are the same directory; pass --source when running from a target project." >&2
  exit 2
fi

if [ ! -f "$manifest" ]; then
  echo "Missing manifest: $manifest" >&2
  exit 1
fi

if git -C "$target_root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if [ "$allow_dirty" != true ] && [ -n "$(git -C "$target_root" status --porcelain --untracked-files=all)" ]; then
    echo "Target git worktree is dirty. Commit/stash first, or rerun with --allow-dirty." >&2
    exit 1
  fi
else
  echo "Target is not a git repository. Harness review requires git; refusing update." >&2
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

  if [ "$dry_run" = true ]; then
    echo "would update: $rel"
    return 0
  fi

  if [[ "$rel" == */ ]]; then
    mkdir -p "$dst"
    rsync -a "$src" "$dst"
  else
    mkdir -p "$(dirname -- "$dst")"
    cp "$src" "$dst"
  fi
  echo "updated: $rel"
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
mode: update
updated_at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
VERSION
  echo "wrote: .harness-version"
}

while IFS= read -r rel; do
  copy_path "$rel"
done < <(list_section harness_owned)

write_version

echo "Harness update complete: $target_root"
echo "Review target diff before committing."
