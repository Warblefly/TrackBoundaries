#!/usr/bin/env python3
import subprocess, sys, os, shlex, pathlib, re

ROOT_DIR = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(".")
KEEP_BACKUPS = True
ERROR_RE = re.compile(r"(invalid sync|error while decoding|crc|corrupt|non-monoton|Invalid data|malformed)", re.IGNORECASE)

def run(cmd):
    # returns (rc, stdout, stderr)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate()
    return p.returncode, out, err

def audio_codecs_are_all_flac(path):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_name", "-of", "csv=p=0", "--", str(path)]
    rc, out, err = run(cmd)
    if rc != 0: return False
    lines = [l.strip().lower() for l in out.splitlines() if l.strip()]
    if not lines: return False
    return all(l == "flac" for l in lines)

def decode_has_errors(path):
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-hide_banner", "-i", str(path), "-map", "0:a", "-f", "null", "-"]
    rc, out, err = run(cmd)
    return bool(ERROR_RE.search(err))

def reencode_flac_preserve(path, out_tmp):
    cmd = [
        "ffmpeg", "-nostdin", "-hide_banner", "-y", "-i", str(path),
        "-map", "0",
        "-map_metadata", "0",
        "-map_chapters", "0",
        "-c", "copy",
        "-c:a", "flac", "-compression_level", "12",
        str(out_tmp)
    ]
    rc, out, err = run(cmd)
    return rc == 0

def main():
    for p in ROOT_DIR.rglob("*.mka"):
        print(f"→ Checking: {p}")
        if not audio_codecs_are_all_flac(p):
            print("   Skipping: Audio codec is not exclusively FLAC (or no audio).")
            continue

        if not decode_has_errors(p):
            print("   ✓ OK (no decode errors).")
            continue

        print("   ✗ Broken FLAC detected (decode errors found).")
        out_tmp = p.with_name(f".reflac.{p.name}.tmp.mka")

        print("   → Re-encoding audio to FLAC (compression_level=12), preserving metadata/chapters/attachments…")
        if not reencode_flac_preserve(p, out_tmp):
            print("   ⚠ ffmpeg failed; leaving original.")
            if out_tmp.exists(): out_tmp.unlink()
            continue

        if decode_has_errors(out_tmp):
            print("   ⚠ Re-encoded file still has decode errors; leaving original.")
            out_tmp.unlink(missing_ok=True)
            continue

        backup = p.with_suffix(p.suffix + ".bak")
        print(f"   → Replacing original (backup: {backup})")
        p.rename(backup)
        out_tmp.rename(p)

        if not KEEP_BACKUPS and backup.exists():
            backup.unlink()
            print("   Backup removed.")
        else:
            print(f"   Backup retained: {backup}")

        print(f"   ✓ Repaired: {p}")

    print("All done.")

if __name__ == "__main__":
    main()
