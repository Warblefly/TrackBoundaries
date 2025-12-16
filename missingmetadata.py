#!/usr/bin/env python3
import os
import argparse
import json
import subprocess
import os.path
import string
import glob
import tempfile
import re
from typing import Optional, Dict, Any, Tuple, List

# Version embedded in MISSINGMETADATAVERSION tag
VERSION = "0.4"
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"


# Punctuation set (brackets intentionally excluded)
_END_PUNCT = "\"#$%&*+.,-/:;<=>@\\^_`|~ "

# MD5-like 32 hex tokens
_MD5_HEX_RE = re.compile(r'(?i)\b[0-9a-f]{32}\b')
_MD5_SEP_HEX_RE = re.compile(r'(?i)[\.\-_]\s*[0-9a-f]{32}\b')
_MD5_SEP_HEX_END_RE = re.compile(r'(?i)[\.\-_]\s*[0-9a-f]{24,32}\s*$')

# Any [ ... ] block
_BRACKETED_ANY_RE = re.compile(r'\[[^\]]*\]')

# Help to preserve MD5 hashes before removal
_TRAILING_HEX_SEP_RE = re.compile(r'(?i)[\.\-_]\s*[0-9a-f]{24,32}\s*$')

# ---------- Utilities ----------

def parse_version_tuple(s: Optional[str]) -> Optional[Tuple[int, ...]]:
    if not s:
        return None
    try:
        parts = [int(p) for p in s.strip().split(".") if p.isdigit()]
        return tuple(parts) if parts else None
    except Exception:
        return None

def version_is_older(existing: Optional[str], current: str) -> bool:
    """Return True if existing is None or a lower version than current."""
    cur_t = parse_version_tuple(current)
    old_t = parse_version_tuple(existing)
    if cur_t is None:
        return False
    if old_t is None:
        return True
    max_len = max(len(old_t), len(cur_t))
    old_t += (0,) * (max_len - len(old_t))
    cur_t += (0,) * (max_len - len(cur_t))
    return old_t < cur_t

def run_cmd(cmd: List[str]) -> Tuple[int, str]:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        return 0, out.decode("utf-8", errors="replace")
    except subprocess.CalledProcessError as e:
        return e.returncode, e.output.decode("utf-8", errors="replace")

def safe_temp_with_suffix(suffix: str) -> str:
    tf = tempfile.NamedTemporaryFile(delete=False)
    tf.close()
    path = tf.name
    if suffix:
        new_path = path + suffix
        os.replace(path, new_path)
        return new_path
    return path

def remove_md5_hashes(s: str) -> str:
    if s is None:
        return ""
    # Remove truncated tail form first (end of string)
    s = _MD5_SEP_HEX_END_RE.sub('', s)
    s = _MD5_SEP_HEX_RE.sub('', s)
    s = _MD5_HEX_RE.sub('', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def remove_bracketed_catalog_numbers(s: str, min_digits: int = 8) -> str:
    """
    Remove square-bracketed catalogue numbers (≥8 digits, only digits/space/_/- inside).
    Preserve text labels like [Live], [Remix].
    """
    if s is None:
        return ""
    def _repl(m: re.Match) -> str:
        content = m.group(0)[1:-1]
        digits = sum(c.isdigit() for c in content)
        if digits >= min_digits and re.fullmatch(r'[\d\s\-_]+', content):
            return ''   # drop the whole bracketed block
        return m.group(0)  # keep non-numeric brackets
    s = _BRACKETED_ANY_RE.sub(_repl, s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def _final_tidy(s: str) -> str:
    if s is None:
        return ""
    s = s.strip()
    s = s.rstrip(_END_PUNCT)
    s = s.lstrip(_END_PUNCT)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def clean_final(value: str) -> str:
    """
    Safe final cleaner: strip bracketed catalogue numbers and MD5 hashes,
    tidy punctuation/whitespace. If result becomes empty, fallback to the
    original with only hash removal. NEVER returns None.
    """
    orig = value or ""  # make sure we start with a string
    s1 = remove_bracketed_catalog_numbers(orig)
    s2 = remove_md5_hashes(s1)
    s3 = _final_tidy(s2)
    if s3 == "":
        # Fallback prevents accidental full erase from aggressive removal
        s3 = _final_tidy(remove_md5_hashes(orig))
    return s3

def _simple_norm(s: str) -> str:
    """Lowercase, remove non-alphanumerics (except spaces), collapse whitespace."""
    if not s:
        return ""
    return re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()

def _token_set(s: str) -> set:
    """Tokenize into a set of words."""
    return set(_simple_norm(s).split())

def filename_resembles_artist(filename_str: str, artist_str: str, threshold: float = 0.6) -> bool:
    """
    Return True if the filename string resembles the artist string,
    based on token overlap ratio relative to artist tokens.

    ratio = |tokens(filename) ∩ tokens(artist)| / |tokens(artist)|
    """
    fn_tokens = _token_set(filename_str)
    artist_tokens = _token_set(artist_str)
    if not fn_tokens or not artist_tokens:
        return False
    overlap = len(fn_tokens & artist_tokens)
    ratio = overlap / max(1, len(artist_tokens))
    return ratio >= threshold



# ---------- Core logic ----------

def filePrefix(filename: str, skip_hash: bool = False) -> str:
    """
    Return basename without extension; if skip_hash=True and the name contains
    an extra dot-delimited hash before the extension, remove that trailing piece.
    Example:
      "Artist - Title.abcdef12.mp3" -> "Artist - Title" when skip_hash=True
    """
    base = os.path.basename(filename)
    name, _ext = os.path.splitext(base)
    if skip_hash and "." in name:
        head, tail = name.rsplit(".", 1)
        if re.fullmatch(r"[A-Za-z0-9]{6,32}", tail):
            return head
    return name

def replaceMetadata(filename: str, artist: Optional[str] = "", title: Optional[str] = "") -> bool:
    artist = "" if artist is None else artist
    title  = "" if title is None else title

    fileExtension = os.path.splitext(filename)[1]
    tempFile = safe_temp_with_suffix(fileExtension)

    # Keep all streams, copy only, set container metadata
    cmd = [
        FFMPEG,
        "-hide_banner", "-loglevel", "error",
        "-i", filename,
        "-map", "0",
        "-c", "copy",
        "-metadata", f"title={title}",
        "-metadata", f"artist={artist}",
        "-metadata", f"MISSINGMETADATAVERSION={VERSION}",
        "-y",
        tempFile
    ]

    if fileExtension.lower() == ".mp3":
        cmd = cmd[:-1] + ["-id3v2_version", "3"] + cmd[-1:]

    rc, out = run_cmd(cmd)
    if rc != 0:
        print(f"FFmpeg failed for {filename}:\n{out}")
        try:
            if os.path.exists(tempFile):
                os.remove(tempFile)
        except Exception:
            pass
        return False

    try:
        os.replace(tempFile, filename)
    except Exception as e:
        print(f"Failed to replace original with temp for {filename}: {e}")
        try:
            if os.path.exists(tempFile):
                os.remove(tempFile)
        except Exception:
            pass
        return False

    return True

def _collect_tags_lower(ff_json: Dict[str, Any]) -> Dict[str, str]:
    tags = {}
    fmt = ff_json.get("format", {})
    if "tags" in fmt and isinstance(fmt["tags"], dict):
        for k, v in fmt["tags"].items():
            tags[k.lower()] = v

    for st in ff_json.get("streams", []):
        if "tags" in st and isinstance(st["tags"], dict):
            for k, v in st["tags"].items():
                tags[k.lower()] = v

    return tags

def getMetadata(filename: str) -> Optional[Dict[str, Optional[str]]]:
    cmd = [
        FFPROBE,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        filename
    ]
    rc, out = run_cmd(cmd)
    if rc != 0:
        print(f"File {filename} might not be a media file (ffprobe error).")
        return None

    try:
        info = json.loads(out)
    except json.JSONDecodeError:
        print(f"ffprobe did not return valid JSON for {filename}")
        return None

    tags = _collect_tags_lower(info)

    def first_of(keys: List[str]) -> Optional[str]:
        for k in keys:
            v = tags.get(k)
            if v:
                return v
        return None

    artist = first_of(["artist", "album_artist", "author", "performer"])
    title  = first_of(["title", "track", "name"])
    version = first_of(["missingmetadataversion", "misingmetadataversion"])
    handler = first_of(["handler_name", "handler", "encoder"])

    return {"artist": artist, "title": title, "version": version, "handler": handler}

# --- Sanitizers ---

_YT_SUFFIX_RE = re.compile(r"""
    (.*?)                # main part
    \s*-\s*              # dash separator
    ([A-Za-z0-9_-]{6,15})# YouTube-like id (no spaces)
    \s*$                 # end
""", re.VERBOSE)

def removeYouTubeSuffix(filename: str, handler: Optional[str] = None) -> str:
    if not handler:
        return filename
    if ("Google" in handler) or ("SoundHandler" in handler) or ("YouTube" in handler):
        m = _YT_SUFFIX_RE.match(filename)
        if m:
            return m.group(1)
    return filename

def removeEndNumber(filename: str, limit: int = 4) -> str:
    clean = filename.rstrip(string.digits)
    if len(clean) <= len(filename) - limit:
        return clean
    else:
        return filename

def removeFrontNumber(filename: str, limit: int = 1) -> str:
    clean = filename.lstrip(string.digits)
    if len(clean) <= len(filename) - limit:
        return clean
    else:
        return filename

_END_PUNCT = "\"#$%&*+.,-/:;<=>@\\^_`|~ "  # brackets intentionally excluded

def removeEndPunctuation(filename: str) -> str:
    return filename.rstrip(_END_PUNCT)

def removeFrontPunctuation(filename: str) -> str:
    return filename.lstrip(_END_PUNCT)

def normalize_dashes(s: str) -> str:
    return s.replace("–", "-").replace("—", "-")

def sanitizeString(filename: str, handler: Optional[str] = None) -> str:
    s = filename
    s = removeYouTubeSuffix(s, handler)
    
    # Remove trailing ./_/- followed by 24–32 hex chars BEFORE stripping numbers
    # This catches full MD5 (32) and fragments (e.g. 28) resulting from later number-strip
    s = _TRAILING_HEX_SEP_RE.sub('', s)

    s = removeEndNumber(s)
    s = removeEndPunctuation(s)
    s = removeEndNumber(s)
    s = removeEndPunctuation(s)

    s = removeFrontNumber(s)
    s = removeFrontPunctuation(s)
    s = removeFrontNumber(s)
    s = removeFrontPunctuation(s)

    s = s.replace("_", " ")
    s = normalize_dashes(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def generateMetadata(filename: str, handler: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    sanitized = sanitizeString(filename, handler)
    parts = [p.strip() for p in sanitized.rsplit("-", 1)]
    parts = [string.capwords(p) for p in parts]
    parts = [sanitizeString(p) for p in parts]
    if len(parts) < 2:
        parts.append(None)
    artist, title = parts[0], parts[1]
    return artist, title

def makeFilenameList(patterns: List[str]) -> List[str]:
    results = []
    for pat in patterns:
        if os.path.exists(pat):
            results.append(pat)
        else:
            results.extend(glob.glob(pat))
    seen = set()
    uniq = []
    for p in results:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq

# ---------- CLI ----------

parser = argparse.ArgumentParser(description='Fill in missing metadata for media files, derived from filename.')
parser.add_argument('pattern', nargs='*', help='Filename(s) or glob(s) to examine/modify.')
parser.add_argument('-m', '--insert', action='store_true', help='Insert metadata if missing.')
parser.add_argument('-f', '--force', action='store_true', help='Force replacement even if existing/newer.')
parser.add_argument('-u', '--skip-hash', action='store_true', help='Disregard unique hash before extension.')
parser.add_argument('-n', '--dry-run', action='store_true', help='Do not write changes; show what would be done.')
args = parser.parse_args()

PATTERN = args.pattern
INSERT = args.insert
FORCE = args.force
SKIP_HASH = args.skip_hash
DRYRUN = args.dry_run

files = makeFilenameList(PATTERN)
filesTotal = len(files)
print(f"Preparing to process {filesTotal} files...")

for idx, filename in enumerate(files, 1):
    print(f"\n[{idx}/{filesTotal}] {filename}")
    meta = getMetadata(filename)
    if not meta:
        continue

    # Version guard (skip newer/equal unless forced)
    newer_or_equal = meta.get('version') and not version_is_older(meta.get('version'), VERSION)
    if newer_or_equal and not FORCE:
        print(f"  - Skipping (metadata version present and not older): existing {meta.get('version')}, tool {VERSION}")
        continue

    need_artist = not meta.get('artist')
    need_title  = not meta.get('title')

    if not (need_artist or need_title) and not FORCE:
        print("  - Metadata already present; not modifying.")
        continue


    prefix  = filePrefix(filename, skip_hash=SKIP_HASH)
    handler = meta.get('handler')

    # Initial derivation using your split logic (artist - title)
    gen_artist, gen_title = generateMetadata(prefix, handler)

    # Existing metadata presence
    existing_artist = meta.get('artist') or ""
    existing_title  = meta.get('title')  or ""

    need_artist = not existing_artist
    need_title  = not existing_title

    # --- Title-only candidate from filename (no split) ---
    # This is used when we want to derive just a title, keeping existing artist.
    title_only_candidate = sanitizeString(prefix, handler)
    title_only_candidate = clean_final(title_only_candidate)

    # --- Smart fallback logic ---
    if need_artist and need_title:
        # No existing metadata at all -> use generated
        final_artist_raw = gen_artist or ""
        final_title_raw  = gen_title  or ""
    elif (not need_artist) and need_title:
        # Artist exists, title missing
        # If filename does NOT resemble the artist, treat entire sanitized filename as the title
        if not filename_resembles_artist(title_only_candidate, existing_artist):
            final_artist_raw = existing_artist                # keep artist
            final_title_raw  = title_only_candidate or gen_title or ""  # derive title-only
        else:
            # Filename resembles artist; fall back to generated split
            final_artist_raw = existing_artist
            final_title_raw  = gen_title or title_only_candidate or ""
    else:
        # Other cases:
        # - Artist missing but title exists
        # - Both exist (and FORCE may be set)
        final_artist_raw = (gen_artist if (need_artist or FORCE) else existing_artist)
        final_title_raw  = (gen_title  if (need_title  or FORCE) else existing_title)

    # ---- Final cleanup on both fields; NEVER returns None ----
    final_artist = clean_final(final_artist_raw)
    final_title  = clean_final(final_title_raw)


    print(f"  Existing: artist={meta.get('artist')!r}, title={meta.get('title')!r}, version={meta.get('version')!r}, handler={meta.get('handler')!r}")
    print(f"  Derived : artist={gen_artist!r}, title={gen_title!r} (from prefix: {prefix!r})")
    print(f"  Planned : artist={final_artist!r}, title={final_title!r}")

    if DRYRUN:
        if INSERT or FORCE:
            print("  Action : [dry-run] Would update metadata (no write).")
        else:
            print("  Action : [dry-run] -m/--insert not set; would NOT write.")
        continue

    if INSERT or FORCE:
        ok = replaceMetadata(filename, artist=final_artist or "", title=final_title or "")
        if ok:
            print("  ✔ Updated metadata.")
        else:
            print("  ✖ Failed to update metadata.")
    else:
        print("  Instructed not to add metadata (-m/--insert not set).")
