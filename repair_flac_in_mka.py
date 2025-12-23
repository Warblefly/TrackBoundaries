#!/usr/bin/env python3
"""
SCRIPT SUMMARY:
This tool scans a directory tree for corrupted FLAC audio streams within MKA (Matroska Audio) files.
When corruption is detected, it re-encodes the FLAC audio to repair it while preserving all metadata,
chapters, and attachments. Original files are backed up as .bak files.

KEY STEPS:
1. Recursively find all . mka files in the specified directory
2. Check if all audio streams are FLAC format (skip if mixed codecs)
3. Attempt to decode to detect errors (FLAC corruption, CRC mismatches, etc.)
4. If errors are found, re-encode the FLAC audio with compression_level=12
5. Verify the re-encoded file decodes without errors
6. Replace the original and optionally keep/remove the backup
"""

import subprocess, sys, os, shlex, pathlib, re

# Root directory to recursively search for . mka files (defaults to current directory)
ROOT_DIR = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(".")

# Whether to retain backup files after successful repair (set to False to delete backups)
KEEP_BACKUPS = True

# Regular expression to detect FLAC decoding errors in ffmpeg stderr output
# Matches keywords like:  invalid sync, CRC errors, corrupt data, non-monotonic timestamps, etc.
ERROR_RE = re.compile(r"(invalid sync|error while decoding|crc|corrupt|non-monoton|Invalid data|malformed)", re.IGNORECASE)


def run(cmd):
    """
    Execute a shell command and capture its output.
    
    Args:
        cmd: List of command arguments (passed to Popen)
    
    Returns:
        Tuple of (return_code, stdout_text, stderr_text)
    """
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess. PIPE, text=True)
    out, err = p.communicate()
    return p.returncode, out, err


def audio_codecs_are_all_flac(path):
    """
    Check if all audio streams in a file are FLAC codec.
    
    Uses ffprobe to query the audio codec for each audio stream.
    Returns False if:  ffprobe fails, no audio streams found, or non-FLAC codecs present.
    
    Args:
        path: Path to the media file to check
    
    Returns: 
        Boolean:  True only if all audio streams are FLAC, False otherwise
    """
    # ffprobe command to list all audio stream codec names
    cmd = ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_name", "-of", "csv=p=0", "--", str(path)]
    rc, out, err = run(cmd)
    
    # If ffprobe failed, assume the file is not safe to process
    if rc != 0: 
        return False
    
    # Parse output:  one codec per line, strip whitespace, convert to lowercase
    lines = [l.strip().lower() for l in out.splitlines() if l.strip()]
    
    # If no audio streams exist, return False (nothing to repair)
    if not lines:  
        return False
    
    # Only return True if ALL audio streams are FLAC (no mixed codecs)
    return all(l == "flac" for l in lines)


def decode_has_errors(path):
    """
    Test-decode the audio streams to detect FLAC corruption errors.
    
    Attempts to decode all audio streams to /dev/null (null muxer).
    Searches stderr for common FLAC error keywords (see ERROR_RE regex).
    
    Args:
        path: Path to the media file to test-decode
    
    Returns: 
        Boolean: True if decode errors detected, False if decode succeeds cleanly
    """
    # ffmpeg command:  decode audio, output to null muxer (no file created)
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-hide_banner", "-i", str(path), "-map", "0:a", "-f", "null", "-"]
    rc, out, err = run(cmd)
    
    # Check if stderr contains any of the known FLAC error patterns
    return bool(ERROR_RE.search(err))


def reencode_flac_preserve(path, out_tmp):
    """
    Re-encode FLAC audio streams to repair corruption while preserving all metadata.
    
    Uses ffmpeg to: 
    - Copy all non-audio streams as-is (video, subtitles, attachments)
    - Copy all metadata and chapter information
    - Re-encode audio streams to FLAC with compression_level=12 (maximum compression)
    
    Args:
        path: Input file path
        out_tmp:  Temporary output file path
    
    Returns:
        Boolean: True if ffmpeg succeeded (rc==0), False if it failed
    """
    cmd = [
        "ffmpeg", "-nostdin", "-hide_banner", "-y",
        "-i", str(path),           # Input file
        "-map", "0",               # Map all streams from input 0
        "-map_metadata", "0",      # Copy all metadata
        "-map_chapters", "0",      # Copy all chapter information
        "-c", "copy",              # Copy non-audio streams as-is
        "-c:a", "flac",            # Encode audio to FLAC
        "-compression_level", "12", # Maximum compression (slowest, but best size)
        str(out_tmp)               # Output file
    ]
    rc, out, err = run(cmd)
    
    # Return success only if ffmpeg exited with code 0
    return rc == 0


def main():
    """
    Main entry point:  scan directory tree and repair corrupted FLAC files.
    
    Process:
    1. Find all .mka files recursively in ROOT_DIR
    2. Skip files with non-FLAC audio or no audio streams
    3. Skip files with no decode errors (already healthy)
    4. Re-encode corrupted files and verify the result
    5. Replace original with repaired version, optionally keeping backup
    """
    # Recursively search for all .mka files (Matroska Audio container)
    for p in ROOT_DIR.rglob("*.mka"):
        print(f"→ Checking: {p}")
        
        # Skip if the file contains non-FLAC audio or is not a valid audio file
        if not audio_codecs_are_all_flac(p):
            print("   Skipping: Audio codec is not exclusively FLAC (or no audio).")
            continue

        # Skip if the file decodes cleanly with no errors
        if not decode_has_errors(p):
            print("   ✓ OK (no decode errors).")
            continue

        # File has corruption; attempt to repair it
        print("   ✗ Broken FLAC detected (decode errors found).")
        
        # Create temporary output filename (prefixed with .  to keep it hidden during processing)
        out_tmp = p.with_name(f".reflac.{p.name}.tmp.mka")

        # Re-encode the FLAC audio with maximum compression
        print("   → Re-encoding audio to FLAC (compression_level=12), preserving metadata/chapters/attachments…")
        if not reencode_flac_preserve(p, out_tmp):
            print("   ⚠ ffmpeg failed; leaving original.")
            if out_tmp.exists(): 
                out_tmp.unlink()
            continue

        # Verify the re-encoded file actually fixed the problems
        if decode_has_errors(out_tmp):
            print("   ⚠ Re-encoded file still has decode errors; leaving original.")
            out_tmp.unlink(missing_ok=True)
            continue

        # Repair was successful; swap the files and create backup
        backup = p.with_suffix(p.suffix + ".bak")
        print(f"   → Replacing original (backup: {backup})")
        
        # Rename original to .bak (atomic operation, creates backup)
        p.rename(backup)
        
        # Rename temporary re-encoded file to original name
        out_tmp.rename(p)

        # Clean up backup if configured, otherwise keep it
        if not KEEP_BACKUPS and backup.exists():
            backup.unlink()
            print("   Backup removed.")
        else:
            print(f"   Backup retained: {backup}")

        print(f"   ✓ Repaired: {p}")

    print("All done.")


if __name__ == "__main__": 
    main()
