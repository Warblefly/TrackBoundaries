#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-.}"                  # default: current directory (use first arg to change)
OUTFILE="${2:-bad_media_files.txt}" # default: bad_media_files.txt (use second arg to change)

# Clean/create output file
: > "$OUTFILE"

# Use a temp directory for stderr captures
TMPDIR="$(mktemp -d)"
cleanup() { rm -rf "$TMPDIR"; }
trap cleanup EXIT

check_file() {
  local f="$1"
  local errlog="$TMPDIR/$(uuidgen 2>/dev/null || date +%s%N).log"

  # 1) Quick container/stream sanity check (ffprobe)
  if ! ffprobe -v error -hide_banner \
      -select_streams v:a:s \
      -show_entries stream=index \
      -of csv=p=0 "$f" > /dev/null 2>&1; then
    printf '%s\n' "$f" >> "$OUTFILE"
    return
  fi

  # 2) Full decode to null muxer to catch decode-time errors:
  #    -v error           => only show errors (suppress warnings/info)
  #    -xerror            => abort on first error (non-zero exit)
  #    -err_detect explode+crccheck => be strict on bitstream issues
  #    -f null -          => decode but don’t write output
  #    -nostdin, -nostats => avoid interactive prompts / noise
  if ! ffmpeg -v error -hide_banner -nostats -nostdin \
      -err_detect explode+crccheck -xerror \
      -i "$f" -f null - 2> "$errlog"; then
    # Non-zero exit: error detected
    printf '%s\n' "$f" >> "$OUTFILE"
    return
  fi

  # Sometimes ffmpeg exits 0 but still prints lines at error level—
  # we already filtered to -v error, so any output here is an error.
  if [[ -s "$errlog" ]]; then
    printf '%s\n' "$f" >> "$OUTFILE"
  fi
}

export -f check_file
export OUTFILE
export TMPDIR

# Traverse all files (null-delimited for safety with spaces/newlines in names)
# You can filter extensions if desired; for now we try all regular files.
find "$ROOT_DIR" -type f -print0 \
| while IFS= read -r -d '' f; do
    check_file "$f"
  done

echo "Done. Files with errors (if any) are listed in: $OUTFILE"
