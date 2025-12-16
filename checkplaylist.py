#!/usr/bin/python3
# This is a MODULE

import os
import argparse
import tempfile
import re
import shutil
from typing import Optional, Tuple, List, Dict


# --- Helpers ---

# 32-hex MD5 token anywhere in the basename, case-insensitive
_MD5_RE = re.compile(r'(?i)\b[a-f0-9]{32}\b')


# Performs a number of playlist and music directory checking options
# such as ensuring a m3u8 playlist's files can all be found,
# or ensuring every music file in a directory has a matching entry in a given playlist.
from typing import Optional, Dict, List


def filenamesfromm3u8(playlist: str):
    filenames = []
    with open(playlist, 'r', encoding='utf-8-sig') as pl:
        for line in pl:
            #print(line.strip())
            if line.startswith('#'):
                continue
            # Everything after the last colon in a line is the filename.
            # If there's no colon, then the line is the filename
            lastcolon = line.rfind(":")
            if lastcolon == -1:
                filenames.append(line.strip())
            else:
                filenames.append(line[lastcolon + 1:].strip())
    #print("Filenames are %s" % filenames)
    return filenames


def findhash(path: str) -> Optional[str]:
    """
    Extract a 32-character hex token from the basename of 'path'.
    Returns None if not found.
    """
    base = os.path.basename(path or "")
    m = _MD5_RE.search(base)
    return m.group(0) if m else None

    

def playlistedfilesmissingfromdirectory(playlist, directory):
    # Need to build a list of files expected from a playlist
    files = filenamesfromm3u8(playlist)
    #print(files)
    errors = []
    for item in files:
        if not os.path.isfile(item):
            errors.append(item)
    return (errors)


def filesmissingfromplaylist(directory, playlist):
    # Need to build a list of files in a directory, expected to be found in a playlist
    errors = []
    files = filenamesfromm3u8(playlist)
    for filename in os.listdir(directory):
        fullpath = os.path.join(directory, filename)
        if fullpath not in files:
            errors.append(filename)
    return(errors)


def parse_playlist_line(line: str) -> Optional[Tuple[str, str]]:
    """
    Parse a playlist line.

    Supports:
      - 'annotate:...key="value",...:/full/path/file.mka'
      - '/full/path/file.mka'

    Behavior:
      - Skips blank lines and lines starting with '#', e.g. '#EXTM3U'.
      - Returns (annotation, filename); 'annotation' may be '' when none is present.
      - Returns None for lines that should be ignored.
    """
    s = (line or "").strip()
    if not s or s.startswith('#'):
        return None
    try:
        annot, fname = s.rsplit(':', 1)  # split at the last colon only
        fname = fname.strip()
        if not fname:
            # A line ending with ':' is malformed; ignore it
            return None
        return (annot, fname)
    except ValueError:
        # No colon → whole line is the filename (no annotation)
        return ('', s)



def weedplaylist(playlist: str, filelist: List[str]):
    """
    Remove entries from a playlist for files whose MD5 hashes appear in `filelist`,
    move those files into a temporary directory under the current working directory,
    and return two lists:

      removedlist:
        - Each element is either 'annotation:/abs/new/path.mka' (if annotation present)
          or '/abs/new/path.mka' (if no annotation).
      weededplaylist:
        - The remaining entries in their original format:
          'annotation:/original/path.mka' OR '/original/path.mka'

    Matching is done by a 32-hex MD5 token found in the basename of the filename.
    """
    # Create temp dir in CWD 
    tempdir = tempfile.mkdtemp(prefix='moved_files_', dir='.')
    print(f"Moving files into {tempdir}.")

    # Build mapping: hash -> [annotation, filename]
    workingdictionary: Dict[str, List[str]] = {}
    removedlist: List[str] = []

    # Use 'utf-8-sig' so a BOM on first line doesn't pollute parsing (#EXTM3U often has BOM)
    with open(playlist, 'r', encoding='utf-8-sig') as pl:
        for raw_line in pl:
            parsed = parse_playlist_line(raw_line)
            if not parsed:
                continue
            annot, fname = parsed
            h = findhash(fname)
            if not h:
                # No detectable hash → skip this entry (or choose a different policy if desired)
                # print(f"Warning: no hash found in '{fname}', skipping this playlist entry.")
                continue
            # NOTE: If multiple entries share the same hash, the later one overwrites the earlier.
            # Could change this to list per hash if I want to store multiple filenames.
            workingdictionary[h] = [annot, fname]

    print("workingdictionary is", workingdictionary)

    # Remove/move files whose hashes match entries in filelist
    for filetoremove in filelist:
        h = findhash(filetoremove)
        if not h:
            print(f"Warning: no hash found in '{filetoremove}', skipping.")
            continue

        entry = workingdictionary.get(h)
        if not entry:
            print(f"Warning: hash '{h}' not present in playlist, skipping.")
            continue

        annot, fname = entry
        dest = os.path.join(tempdir, os.path.basename(fname))
        print(f"Renaming {fname} to {dest}")

        try:
            # Use shutil.move to support cross-filesystem moves (os.rename may fail with EXDEV)
            shutil.move(fname, dest)
        except FileNotFoundError:
            print(f"Warning: source file not found: {fname}; removing entry from playlist anyway.")
        except Exception as e:
            print(f"Error moving '{fname}' → '{dest}': {e}")
            # On failure, keep in playlist and continue
            continue

        removed_abs = os.path.abspath(dest)

        # Preserve original formatting: include annotation only if it existed
        if annot:
            removedlist.append(f"{annot}:{removed_abs}")
        else:
            removedlist.append(removed_abs)

        # Remove from working set (i.e., from the remaining playlist)
        workingdictionary.pop(h, None)

    # Rebuild the weeded playlist, preserving original formatting per entry
    weededplaylist: List[str] = []
    for annot, fname in workingdictionary.values():
        if annot:
            weededplaylist.append(f"{annot}:{fname}")
        else:
            weededplaylist.append(fname)


    return(removedlist, weededplaylist)
