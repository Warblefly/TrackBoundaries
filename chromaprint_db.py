#!/usr/bin/python3

import glob, argparse, subprocess, csv, os, sys

FPCALC = "/usr/local/bin/fpcalc"
FFPROBE = "/usr/local/bin/ffprobe"

def fingerprint(filename, duration):
    print("Examining %s for %s seconds." % (filename, duration))
    test = subprocess.check_output(
        [FPCALC, "-algorithm", "4", "-ignore-errors", "-overlap", "-length", str(duration), "-raw", filename],
        encoding='utf-8'
    ).split('\n')
    chromaprint = test[1].split('=')[1]
    dur = test[0].split('=')[1]
    return {"chromaprint": chromaprint, "dur": int(dur)}

def findDuration(filename):
    print("Testing duration of %s." % filename)
    test = subprocess.check_output(
        [FFPROBE, "-v", "quiet", "-show_entries", "stream_tags=DURATION",
         "-of", "default=noprint_wrappers=1:nokey=1", filename],
        encoding='utf-8'
    ).rstrip('\n')
    (hours, minutes, seconds) = test.split(":")
    seconds = (int(hours) * 3600) + (int(minutes) * 60) + float(seconds)
    print("Duration is %s" % seconds)
    return seconds

def patternToList(pattern):
    return glob.glob(pattern)

def intToBitPairs(number):
    remainder_stack = []
    while number > 0:
        remainder = number % 4
        remainder_stack.append(remainder)
        number = number // 4

    new_digits = []
    while remainder_stack:
        new_digits.append('0123'[remainder_stack.pop()])

    return ''.join(new_digits).zfill(16)

def load_existing_filenames(csv_path):
    """
    Return a set of filenames (first column) already present in the CSV.
    Exact string match is used; paths and case are not normalized.
    """
    existing = set()
    if not os.path.exists(csv_path):
        return existing
    try:
        with open(csv_path, 'r', newline='', encoding='utf-8') as fd:
            reader = csv.reader(fd)
            for row in reader:
                if not row:
                    continue
                # Expect schema: filename, chromaprint, duration
                existing.add(row[0])
    except Exception as e:
        print(f"Warning: could not read existing CSV '{csv_path}': {e}", file=sys.stderr)
    return existing


parser = argparse.ArgumentParser(
    description="Automatically fingerprint file(s) containing audio",
    epilog="For support, contact john@johnwarburton.net"
)
parser.add_argument("files", help="Path of files; shell-style wildcards are accepted.", type=str)
parser.add_argument("-d", "--duration", help="Duration, in seconds, of audio in fingerprint. Default: 30", default=30, type=int)
parser.add_argument("-o", "--output", help="Output database (appends/creates). Default: chromaprints.csv", default="chromaprints.csv", type=str)
args = parser.parse_args()

files = args.files
database = args.output
duration = args.duration

# 1) Collect candidate files and restrict to .mka (single directory)
filenameList = [f for f in patternToList(files) if f.endswith(".mka")]
print("We found %s .mka files." % len(filenameList))

# 2) Load existing filenames from CSV and skip them
existing_filenames = load_existing_filenames(database)
to_process = [f for f in filenameList if f not in existing_filenames]

print("Skipping %s already fingerprinted file(s) in %s." % (len(filenameList) - len(to_process), database))
print("We will fingerprint %s new file(s)." % len(to_process))

if not to_process:
    print("Nothing to do; all matching files already exist in the CSV.")
    sys.exit(0)

# 3) Progress indicator formatting: [xx/nnnn] where nnnn == len(to_process)
total = len(to_process)
width_total = max(4, len(str(total)))  # at least 4 digits for the total, as requested
width_idx = max(2, len(str(total)))    # at least 2 digits for the index

# 4) Append new rows to CSV in a single open
with open(database, 'a', newline='', encoding='utf-8') as fd:
    csvWriter = csv.writer(fd)
    for i, filename in enumerate(to_process, start=1):
        progress = f"[{str(i).zfill(width_idx)}/{str(total).zfill(width_total)}]"
        print(f"{progress} {filename}")

        # Fingerprint the file
        checkFingerprint = fingerprint(filename, duration)

        # Your existing transformation
        chromaprintList = list(map(int, checkFingerprint["chromaprint"].split(",")))
        dur = checkFingerprint["dur"]
        rawBinaryChromaprintList = [intToBitPairs(w) for w in chromaprintList]
        rawBinaryChromaprint = ','.join(rawBinaryChromaprintList)[:3059]

        # Diagnostics (kept as in your original script)
        print("For file %s," % filename)
        print("...we have fingerprint:")
        print(rawBinaryChromaprint)
        print("of length %s" % len(rawBinaryChromaprint))

        # Write the row: filename, chromaprint, duration
        csvWriter.writerow([filename, rawBinaryChromaprint, dur])

print("Done.")
