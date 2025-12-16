#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import time
import argparse
import unicodedata
from difflib import SequenceMatcher
from typing import List, Dict, Optional, Tuple
from collections import Counter

# ---------- Config ----------

AUDIO_EXTS = {
    ".mka", ".mkv", ".mp4", ".opus", ".alac", ".mp3", ".flac", ".fla", ".m4a", ".wav", ".m4p", ".ogg", ".au", ".ape", ".webm", ".aac", ".wma", ".aiff", ".aif"
}

# Trailing separator + 24..32 hex at end (handles full MD5 and truncated tails)
_TRAILING_HEX_SEP_RE = re.compile(r'(?i)[\.\-_]\s*[0-9a-f]{24,32}\s*$')

# ---------- Normalization utilities ----------

def nfc(s: str) -> str:
    """NFC normalize (helps when mixing Windows/macOS/Linux historical filenames)."""
    return unicodedata.normalize('NFC', s or "")

def casefold(s: str) -> str:
    """Case-insensitive normalization: NFC + casefold."""
    return nfc(s).casefold()

def ext_of(path: str) -> str:
    return os.path.splitext(path)[1].lower()

def title_like_from_stem(stem: str) -> str:
    """
    Produce a title-like string by:
    - removing leading track numbers and adjacent punctuation
    - removing trailing hash (already done before calling, but idempotent)
    - converting underscores to spaces
    - collapsing spaces and trimming
    This is lighter than your full sanitizeString but good for indexing & matching.
    """
    s = stem
    # Remove leading track numbers like '01 ', '01.', '01 - '
    s = re.sub(r'^\s*\d+\s*[-\.\)]*\s*', '', s)
    # Remove trailing .-_ + 24..32 hex (if any)
    s = _TRAILING_HEX_SEP_RE.sub('', s)
    # Normalize underscores and dashes
    s = s.replace('_', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# ---------- Indexing ----------

def build_index(roots: List[str], index_path: str) -> None:
    """
    Walk all roots and build a JSONL index of audio files with multiple keys
    for robust resolution.
    """
    if not roots or not index_path:
        return

    count = 0
    with open(index_path, "w", encoding="utf-8") as f:
        for root in roots:
            for dirpath, _, filenames in os.walk(root):
                for name in filenames:
                    full = os.path.join(dirpath, name)
                    ext = ext_of(full)
                    if ext not in AUDIO_EXTS:
                        continue

                    stem, _ = os.path.splitext(name)
                    stem_nohash = _TRAILING_HEX_SEP_RE.sub('', stem)
                    title_like = title_like_from_stem(stem_nohash)

                    rec = {
                        "path": full,
                        "ext": ext,
                        "basename_cf": casefold(name),                  # e.g., "11.jean knight - mr big stuff.opus"
                        "stem_cf": casefold(stem),                      # "11.jean knight - mr big stuff"
                        "stem_nohash_cf": casefold(stem_nohash),        # "11.jean knight - mr big stuff"
                        "title_like_cf": casefold(title_like),          # "mr big stuff"
                    }
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    count += 1
    print(f"Indexed {count} audio files into {index_path}")

def load_index(index_path: str) -> List[Dict]:
    items: List[Dict] = []
    if not index_path or not os.path.exists(index_path):
        return items
    with open(index_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items

# ---------- Resolution ----------


import os
from difflib import SequenceMatcher

def _same_path(a: str, b: str) -> bool:
    # robust path equality: absolute + realpath + case-insensitive compare
    try:
        ra = os.path.realpath(os.path.abspath(a))
        rb = os.path.realpath(os.path.abspath(b))
        return ra.casefold() == rb.casefold()
    except Exception:
        return os.path.abspath(a).casefold() == os.path.abspath(b).casefold()

def resolve_path(query_path: str, index: list[dict], allow_self: bool = False) -> str | None:
    """
    Resolve a possibly non-existent 'derived' path to an existing original.

    Matching order (all case-insensitive):
      1) exact stem_nohash_cf
      2) exact title_like_cf
      3) exact basename_cf
      4) fuzzy title_like_cf (>= 0.92)

    Self-mapping (query -> query) is avoided unless allow_self=True.
    """
    base = os.path.basename(query_path)
    stem, _ext = os.path.splitext(base)

    # Strip trailing ./_/- + 24..32 hex early to avoid truncation later
    stem_nohash = _TRAILING_HEX_SEP_RE.sub('', stem)

    # Build normalized keys
    stem_cf = casefold(stem)
    stem_nohash_cf = casefold(stem_nohash)
    title_like = title_like_from_stem(stem_nohash)
    title_like_cf = casefold(title_like)
    basename_cf = casefold(base)

    def acceptable(path: str) -> bool:
        return allow_self or not _same_path(path, query_path)

    # 1) Exact stem_nohash_cf match
    for rec in index:
        if stem_nohash_cf == rec["stem_nohash_cf"] and acceptable(rec["path"]):
            return rec["path"]

    # 2) Exact title_like_cf match
    if title_like_cf:
        for rec in index:
            if title_like_cf == rec["title_like_cf"] and acceptable(rec["path"]):
                return rec["path"]

    # 3) Exact basename_cf match
    for rec in index:
        if basename_cf == rec["basename_cf"] and acceptable(rec["path"]):
            return rec["path"]

    # 4) Fuzzy fallback on title_like_cf
    if title_like_cf:
        best_ratio = 0.0
        best_path = None
        for rec in index:
            r = SequenceMatcher(None, title_like_cf, rec["title_like_cf"]).ratio()
            if r > best_ratio and acceptable(rec["path"]):
                best_ratio, best_path = r, rec["path"]
        if best_ratio >= 0.92:
            return best_path

    # Nothing found.
    # Optional final fallback: if user explicitly allows self and file exists, return it
    if allow_self and os.path.exists(query_path):
        return query_path


# ---------- CLI and main ----------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Map derived/playlist entries to original media files using a JSONL index."
    )
    # Make paths optional so we can support index-only runs
    p.add_argument("paths", nargs="*", help="Input file paths to resolve (can be non-existent derived entries).")
    p.add_argument("--roots", nargs="+", help="Root directories to index for originals.")
    p.add_argument("--index-jsonl", type=str, required=True, help="JSONL index path to create/use.")
    p.add_argument("--reindex", action="store_true", help="Rebuild the index before resolving.")
    p.add_argument("--map-jsonl", type=str, help="Write output mappings to this JSONL file.")
    p.add_argument("--allow-self", action="store_true", help="Allow mapping to the same path if it exists (default: False)")
    p.add_argument("--unresolved-jsonl", type=str, help="Append unresolved file records as JSONL to this path.")
    p.add_argument("--unresolved-log", type=str, help="Append unresolved file messages (plain text) to this path.")
    p.add_argument("--timestamp", action="store_true", help="Include UTC timestamp in unresolved records.")
    p.add_argument("--m3u8-out", type=str, help="Write a UTF-8 M3U8 playlist (#EXTM3U + one resolved path per line) to this file.")
    p.add_argument("-n", "--dry-run", action="store_true", help="Dry-run: print mappings but do not write map file.")
    return p.parse_args()

def write_jsonl(path: str, obj: Dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def append_jsonl(path: str, obj: dict) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def append_text(path: str, line: str) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")

def write_m3u8(out_path: str, tracks: List[str]) -> None:
    """
    Write an M3U8 playlist (UTF-8) with a #EXTM3U header followed by
    one absolute file path per line. Duplicates are suppressed while
    preserving order of first occurrence.
    """
    if not out_path:
        return
    # Deduplicate while preserving order
    seen = set()
    ordered_unique = []
    for t in tracks:
        tc = t.casefold()
        if tc not in seen:
            seen.add(tc)
            ordered_unique.append(t)

    # Write atomically where possible
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("#EXTM3U\n")
        for path in ordered_unique:
            f.write(path.rstrip() + "\n")

def utc_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    args = parse_args()

    # Index-only mode: rebuild index and exit if no paths were provided
    if args.reindex and (not args.paths):
        if not args.roots:
            raise SystemExit("--reindex requires --roots when running in index-only mode.")
        build_index(args.roots, args.index_jsonl)
        print("Index rebuilt. No paths to resolve; exiting.")
        return

    # Load index (build if requested)
    if args.reindex:
        if not args.roots:
            raise SystemExit("--reindex requires --roots")
        build_index(args.roots, args.index_jsonl)

    index = load_index(args.index_jsonl)

    total = len(args.paths)
    resolved_count = 0
    unresolved_count = 0
    resolved_paths_for_playlist: List[str] = []

    print(f"Resolving {total} paths using index: {args.index_jsonl}")


    for i, query in enumerate(args.paths, 1):
        resolved = resolve_path(query, index, allow_self=getattr(args, "allow_self", False))
        print(f"[{i}/{total}] {query}")

        if resolved:
            print(f"  -> {resolved}")
            resolved_count += 1
            resolved_paths_for_playlist.append(resolved)

            # If you also write successful mappings, do it here (optional)
            if args.map_jsonl and not args.dry_run:
                append_jsonl(args.map_jsonl, {"query": query, "resolved": resolved, "ts": utc_ts() if args.timestamp else None})

        else:
            print("  ✖ Could not resolve")
            unresolved_count += 1

            # Build diagnostic fields to help future debugging/searching
            base = os.path.basename(query)
            stem, _ext = os.path.splitext(base)
            stem_nohash = _TRAILING_HEX_SEP_RE.sub('', stem)
            title_like = title_like_from_stem(stem_nohash)

            record = {
                "query": query,
                "basename_cf": casefold(base),
                "stem_cf": casefold(stem),
                "stem_nohash_cf": casefold(stem_nohash),
                "title_like_cf": casefold(title_like),
                "ts": utc_ts() if args.timestamp else None
            }

            # JSONL unresolved
            if args.unresolved_jsonl:
                append_jsonl(args.unresolved_jsonl, record)

            # Plain text unresolved
            if args.unresolved_log:
                append_text(
                    args.unresolved_log,
                    f"{utc_ts() if args.timestamp else ''} UNRESOLVED: {query}\n"
                    f"  basename_cf={record['basename_cf']}\n"
                    f"  stem_nohash_cf={record['stem_nohash_cf']}\n"
                    f"  title_like_cf={record['title_like_cf']}"
                )

    # Summary
    print(f"\nSummary: resolved={resolved_count}, unresolved={unresolved_count}, total={total}")
    
    cf_counts = Counter(p.casefold() for p in resolved_paths_for_playlist)
    dupes = [ (p, c) for p, c in cf_counts.items() if c > 1 ]
    if dupes:
        print("Duplicate resolved targets (case-insensitive):")
        for p_cf, c in sorted(dupes, key=lambda x: -x[1]):
            # Show one original spelling for readability:
            sample = next(s for s in resolved_paths_for_playlist if s.casefold() == p_cf)
            print(f"  {sample}  (appears {c} times)")

    
    # Emit M3U8 playlist if requested (and not dry-run)
    if args.m3u8_out:
        if args.dry_run:
            print(f"(dry-run) Would write M3U8 to: {args.m3u8_out} with {len(set(p.casefold() for p in resolved_paths_for_playlist))} unique entries.")
        else:
            write_m3u8(args.m3u8_out, resolved_paths_for_playlist)
            print(f"M3U8 written: {args.m3u8_out}")


if __name__ == "__main__":
    main()
