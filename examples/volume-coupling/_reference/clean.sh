#!/usr/bin/env bash

# -------------------------------------------------------------------
# Script Name: clean.sh
# Description: Recursively deletes/moves files/dirs except:
#              - Global preserved filenames anywhere (run.sh, adapter-config.json...)
#              - Specific root files (README.md, precice-config.xml)
# Usage: ./clean.sh [--dry-run] [--force]
#   --dry-run : show what would happen, don't remove/move
#   --force   : permanently delete unpreserved items AND remove existing backups
# -------------------------------------------------------------------

# Strict mode:
# -e: exit on error
# -u: exit on undefined variable
# -o pipefail: exit if any command in a pipe fails
set -euo pipefail

# --- CONFIGURATION ---
ROOT_DIR="$(pwd)"
LOG_FILE="cleanup.log"
BACKUP_DIR="$ROOT_DIR/backup_$(date '+%Y%m%d_%H%M%S')"

# 1. GLOBAL PRESERVES: filenames to keep anywhere in the tree
GLOBAL_PRESERVE_NAMES=(
    "run.sh"
    "adapter-config.json"
)

# 2. ROOT PRESERVES: filenames to keep only if in ROOT_DIR
ROOT_PRESERVE_PATHS=(
    "clean.sh"
    "README.md"
    "precice-config.xml"
    "$LOG_FILE"   # always keep the log (will be overwritten)
)

# --- DEFAULTS ---
DRY_RUN=0 # No dry-run by default
FORCE=0 # No permanent removal of files by default
MOVED_COUNT=0 # Counter to track if we actually backed anything up
DELETED_COUNT=0 # Counter to track if we actually deleted anything

# --- HELPERS ---

log() {
    # We use tee -a (append) here so we don't overwrite previous lines *of this run*.
    # The file is cleared once at the start of the MAIN block.
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Is filename (basename) a global preserved name?
is_global_preserved() {
    local filename="$1"
    for name in "${GLOBAL_PRESERVE_NAMES[@]}"; do
        if [[ "$filename" == "$name" ]]; then
            return 0
        fi
    done
    return 1
}

# Is a relative path preserved at root?
is_root_preserved() {
    local relpath="$1"
    for p in "${ROOT_PRESERVE_PATHS[@]}"; do
        if [[ "$relpath" == "$p" ]]; then
            return 0
        fi
    done
    return 1
}

# Find out whether directory contains any preserved file *anywhere* under it.
# Implementation Note: Uses `head -n 1` instead of `-quit` for maximum compatibility
# across all Linux distros (including Alpine/BusyBox) and BSD/MacOS.
dir_contains_preserved_content() {
    local dir="$1"
    local name
    local -a find_args=()

    # Build find arguments: ( -name A -o -name B ... )
    for name in "${GLOBAL_PRESERVE_NAMES[@]}"; do
        if [ ${#find_args[@]} -eq 0 ]; then
            find_args+=( -name "$name" )
        else
            find_args+=( -o -name "$name" )
        fi
    done

    # Check if find returns any match.
    # piping to head -n 1 causes find to receive SIGPIPE and stop early if a match is found.
    if [ -n "$(find "$dir" \( "${find_args[@]}" \) -print 2>/dev/null | head -n 1)" ]; then
        return 0
    fi
    return 1
}

# Ensure backup destination exists and safely move source there preserving relative path.
# Prevents collisions by making unique names if needed.
# Args:
#   $1 = absolute src path
#   $2 = rel path relative to ROOT_DIR (used to recreate path inside backup)
safe_move_to_backup() {
    local src="$1"
    local rel="$2"

    # Destination path = $BACKUP_DIR/$rel
    local dest="$BACKUP_DIR/$rel"
    local dest_dir
    dest_dir="$(dirname "$dest")"

    # Normalize: if dirname is ".", use $BACKUP_DIR as target dir
    if [[ "$dest_dir" == "$BACKUP_DIR/." ]] || [[ "$dest_dir" == "." ]]; then
        dest_dir="$BACKUP_DIR"
    fi

    if [ "$DRY_RUN" -eq 0 ]; then
      mkdir -p "$dest_dir"
    fi

    # If dest exists, append numeric suffix before extension to avoid overwrite
    if [ -e "$dest" ]; then
        local base name ext candidate n
        base="$(basename "$dest")"
        name="${base%.*}"
        ext="${base##*.}"
        n=1

        # Check if file has an extension
        if [[ "$ext" == "$base" ]]; then
            # No extension
            candidate="$dest_dir/${name}_$n"
            while [ -e "$candidate" ]; do
                n=$((n+1))
                candidate="$dest_dir/${name}_$n"
            done
        else
            # Has extension
            candidate="$dest_dir/${name}_$n.$ext"
            while [ -e "$candidate" ]; do
                n=$((n+1))
                candidate="$dest_dir/${name}_$n.$ext"
            done
        fi
        dest="$candidate"
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
        log "Would be deleted: ${rel}"
    else
        mv -- "$src" "$dest"
        # Increment the counter because we successfully moved a file
        MOVED_COUNT=$((MOVED_COUNT + 1))
        log "Deleted: ${rel}"
    fi
}

# Safe remove (used by --force). Respects --dry-run.
safe_remove() {
    local src="$1"
    local rel="$2"
    if [ "$DRY_RUN" -eq 1 ]; then
        log "Would permanently remove: $rel"
    else
        rm -rf -- "$src"
        DELETED_COUNT=$((DELETED_COUNT + 1))
        log "Permanently removed: $rel"
    fi
}

# Remove existing backup_* directories permanently (used when FORCE=1).
remove_existing_backups_permanently() {
    shopt -s nullglob
    local found=0
    for old in "$ROOT_DIR"/backup_*; do
        if [ -d "$old" ]; then
            found=1
            if [ "$DRY_RUN" -eq 1 ]; then
                log "Would permanently remove backup: $(basename "$old")"
            else
                rm -rf -- "$old"
                DELETED_COUNT=$((DELETED_COUNT + 1))
                log "Permanently removed backup: $(basename "$old")"
            fi
        fi
    done
    shopt -u nullglob
    if [ "$found" -eq 0 ]; then
        log "No existing backup directories to remove."
    fi
}

# Perform action for a single path (file or directory) that is NOT preserved.
# Moves to backup preserving tree, or removes permanently when FORCE=1.
perform_action() {
    local item="$1"
    local rel_path="${item#$ROOT_DIR/}"

    if [ "$FORCE" -eq 1 ]; then
        safe_remove "$item" "$rel_path"
    else
        safe_move_to_backup "$item" "$rel_path"
    fi
}

# --- RECURSIVE CLEANUP ---
recursive_cleanup() {
    local current_dir="$1"

    # dotglob: includes hidden files (starting with .)
    # nullglob: makes the loop not run if no files match (avoids literal string issues)
    shopt -s dotglob nullglob

    local item rel_path base

    for item in "$current_dir"/*; do
        # Sanity check: ensure file exists (handles rare race conditions or broken links)
        [ ! -e "$item" ] && [ ! -L "$item" ] && continue

        rel_path="${item#$ROOT_DIR/}"
        base="$(basename "$item")"

        # Skip . and .. (though glob usually excludes them, safety first)
        if [[ "$base" == "." || "$base" == ".." ]]; then
            continue
        fi

        # --- FILE or SYMLINK ---
        if [ -f "$item" ] || [ -L "$item" ]; then
            # 1. Preserve by global name anywhere?
            if is_global_preserved "$base"; then
                log "Preserving: $rel_path"
                continue
            fi

            # 2. Preserve if at root and matches root-preserve list?
            if [[ "$current_dir" == "$ROOT_DIR" ]] && is_root_preserved "$base"; then
                log "Preserving: $rel_path"
                continue
            fi

            # Otherwise: perform action
            perform_action "$item"
            continue
        fi

        # --- DIRECTORY ---
        if [ -d "$item" ]; then
            # Check if dir contains any preserved content anywhere below
            if dir_contains_preserved_content "$item"; then
                recursive_cleanup "$item"

                # After recursion, if directory is empty, remove it (respecting dry-run)
                if [ -z "$(ls -A "$item")" ]; then
                    if [ "$DRY_RUN" -eq 1 ]; then
                        log "Would remove empty directory: $rel_path"
                    else
                        rmdir -- "$item"
                        DELETED_COUNT=$((DELETED_COUNT + 1))
                        log "Removed empty directory: $rel_path"
                    fi
                fi
            else
                # Directory contains no preserved files anywhere deep: remove/move entire directory
                perform_action "$item"
            fi
            continue
        fi
    done

    # Restore defaults for shopt to avoid side effects if function is reused
    shopt -u dotglob nullglob
}

# --- MAIN ---

# Parse flags
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=1 ;;
        --force) FORCE=1 ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Initialize/Clear the log file for this new run
: > "$LOG_FILE"

# Confirmation prompt (skip when dry-run)
if [ "$DRY_RUN" -eq 1 ]; then
    log "Dry run enabled, nothing will be removed."
else
    read -p "This will delete all files except preserved ones. Proceed? [y/n]: " confirm
    case "$confirm" in
        [yY][eE][sS]|[yY]) ;;
        *) log "Cleanup aborted."; exit 0 ;;
    esac
fi

if [ "$FORCE" -eq 1 ] && [ "$DRY_RUN" -eq 1 ]; then
  log "Ignoring --force."
  FORCE=0
fi

log "Starting cleanup..."


if [ "$FORCE" -eq 1 ]; then
    remove_existing_backups_permanently
fi

recursive_cleanup "$ROOT_DIR"

if [ "$DELETED_COUNT" -eq 1 ]; then
    FILE_STR="file"
    DIRECTORY_STR="directory"
else
    FILE_STR="files"
    DIRECTORY_STR="directories"
fi

OUTPUT_STR=""

# Output if FORCE
if [ "$FORCE" -eq 1 ]; then
    OUTPUT_STR="Deleted $DELETED_COUNT $FILE_STR or $DIRECTORY_STR. "
fi

if [ "$DRY_RUN" -eq 1 ]; then
    OUTPUT_STR="Dry-run completed successfully."
else
  OUTPUT_STR="${OUTPUT_STR}Cleanup completed successfully."
fi

# Only append the backup message if we actually moved files (MOVED_COUNT > 0)
if [ "$MOVED_COUNT" -gt 0 ]; then
    # Correct wording
    if [ "$MOVED_COUNT" -eq 1 ]; then
      FILE_STR="file"
      DIRECTORY_STR="directory"
    else
      FILE_STR="files"
      DIRECTORY_STR="directories"
    fi
    OUTPUT_STR="$OUTPUT_STR Backed up $MOVED_COUNT deleted $FILE_STR or $DIRECTORY_STR in '$BACKUP_DIR'."
fi

log "$OUTPUT_STR"