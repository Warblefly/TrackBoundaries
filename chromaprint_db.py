#!/usr/bin/python3

import glob, argparse, subprocess, csv

FPCALC = "/usr/local/bin/fpcalc"
FFPROBE = "/usr/local/bin/ffprobe"

def fingerprint(filename, duration):
    print("Examining %s for %s seconds." % (filename, duration))
    test = subprocess.check_output([FPCALC, "-algorithm", "4", "-overlap", "-length", str(duration), "-raw", filename], encoding='utf-8').split('\n')
    chromaprint = test[1].split('=')[1]
    dur = test[0].split('=')[1]
    return{"chromaprint": chromaprint, "dur": int(dur)}

def findDuration(filename):
    print("Testing duration of %s." % filename)
    test = subprocess.check_output([FFPROBE, "-v", "quiet", "-show_entries", "stream_tags=DURATION", \
            "-of", "default=noprint_wrappers=1:nokey=1", filename], encoding='utf-8').rstrip('\n')
    (hours, minutes, seconds) = test.split(":")
    seconds = (int(hours) * 3600) + (int(minutes) * 60) + float(seconds)
    print("Duration is %s" % seconds)
    return(seconds)

def patternToList(pattern):
    return(glob.glob(pattern))

def intToBitPairs(number):
    remainder_stack = []
    while number > 0:
        remainder = number % 4
        remainder_stack.append(remainder)
        number = number // 4

    new_digits = []
    while remainder_stack:
        new_digits.append('0123'[remainder_stack.pop()])

    return(''.join(new_digits).zfill(16))


parser = argparse.ArgumentParser(description="Automatically fingerprint file(s) containing audio",
        epilog="For support, contact john@johnwarburton.net")
parser.add_argument("files", help="Path of files; shell-style wildcards are accepted.", type=str)
parser.add_argument("-d", "--duration", help="Duration, in seconds, of audio in fingerprint. Default: 30", default=30, type=int)
parser.add_argument("-o", "--output", help="Output database. Always overwritten. Default: chromaprints.csv", default="chromaprints.csv", type=str)
args = parser.parse_args()

files = args.files
database = args.output
duration = args.duration

filenameList = patternToList(files)
print("We will examine %s files." % len(filenameList))


for filename in filenameList:
    checkFingerprint = fingerprint(filename, duration)
    # Take only the first 3059 characters. The silence detection algorithm
    # results in varying-length chromaprints
    # The figure 3059 is arrived by experimentation with a real-world playlist
    # and choosing a common length above which the vast majority of tracks
    # fall.
    chromaprintList = list(map(int, checkFingerprint["chromaprint"].split(",")))
    dur = checkFingerprint["dur"]
    rawBinaryChromaprintList = [intToBitPairs(w) for w in chromaprintList]
    #for item in rawBinaryChromaprintList:
    #    print("len: %s" % len(item))
#    rawBinaryChromaprint = ','.join(rawBinaryChromaprintList)[:1563]
    rawBinaryChromaprint = ','.join(rawBinaryChromaprintList)[:3059]
    print("For file %s," % filename)
    print("...we have fingerprint:")
    print(rawBinaryChromaprint)
    print("of length %s" % len(rawBinaryChromaprint))
    fd = open(database, 'a')
    csvWriter = csv.writer(fd)
    csvWriter.writerow([filename, rawBinaryChromaprint, dur])
    fd.close()

