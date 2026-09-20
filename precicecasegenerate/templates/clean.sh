#!/usr/bin/env bash
set -euo pipefail

# Safely resolve the directory where this script actually lives
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ==========================================
# CONFIGURATION: What to clean up
# ==========================================

# File patterns to delete
FILES_TO_DELETE=(
    "precice-*.log"
    "core"
    "*.vtk"
    "*.vtu"
    "*.frd"
    "*.dat"
    "*.11D"
    "*.sta"
    "*.cvg"
    "*.rout"
)

# Exact folder names to delete completely
DIRS_TO_DELETE=(
    "precice-run"
    "postProcessing"
)

# ==========================================
# LOGIC: Safety Check & Execution
# ==========================================

# Safety Check: Does this look like a preCICE case?
if [ ! -f "$ROOT_DIR/precice-config.xml" ]; then
    echo "Warning: 'precice-config.xml' not found in $ROOT_DIR."
    read -p "This does not look like a standard preCICE case root. Proceed anyway? [y/N]: " confirm
    case "$confirm" in
        [yY][eE][sS]|[yY]) echo "Proceeding..." ;;
        *) echo "Cleanup aborted."; exit 0 ;;
    esac
fi

echo "Cleaning artifacts in $ROOT_DIR..."

# Delete files
if [ ${#FILES_TO_DELETE[@]} -gt 0 ]; then
    FILE_ARGS=()
    for pattern in "${FILES_TO_DELETE[@]}"; do
        if [ ${#FILE_ARGS[@]} -eq 0 ]; then
            FILE_ARGS+=( -name "$pattern" )
        else
            FILE_ARGS+=( -o -name "$pattern" )
        fi
    done

    # Executes: find . -type f \( -name "*.vtk" -o -name "*.log" \) -delete
    find "$ROOT_DIR" -type f \( "${FILE_ARGS[@]}" \) -delete
fi

# Delete directories
if [ ${#DIRS_TO_DELETE[@]} -gt 0 ]; then
    DIR_ARGS=()
    for pattern in "${DIRS_TO_DELETE[@]}"; do
        if [ ${#DIR_ARGS[@]} -eq 0 ]; then
            DIR_ARGS+=( -name "$pattern" )
        else
            DIR_ARGS+=( -o -name "$pattern" )
        fi
    done

    # We use 'rm -rf' here because 'find -delete' refuses to delete non-empty folders
    find "$ROOT_DIR" -type d \( "${DIR_ARGS[@]}" \) -exec rm -rf {} +
fi

# Clean up any leftover empty directories
find "$ROOT_DIR" -mindepth 1 -type d -empty -delete 2>/dev/null || true

echo "Cleanup finished successfully."