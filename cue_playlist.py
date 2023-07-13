#!/usr/bin/python3

import subprocess, argparse, os, os.path, random, string, tempfile, csv
from pathlib import Path

FFMPEG = "/usr/local/bin/ffmpeg"
FPCALC = "/usr/local/bin/fpcalc"
MEZZANINE = "-acodec libfdk_aac -vbr 5 -ac 2 -map 0:a"

def analyse(filename, volDrop, volStart=40, mezzanine=None, forceEncode=False):
    # Analyses file in filename, returns seconds to end-of-file of place where volume last drops to level
    # below average loudness, given in volDrop in LU.
    # Also determines file start, where monentary loudness leaps above a certain point given by volStart
    # Also encode and store a mezzanine file, if a mezzanine directory name is given

    # Make a list containing many points, 1/10 sec apart, where loudness is measured.
    # We need TIME and MOMENTARY LOUDNESS
    # We also need full INTEGRATED LOUDNESS

    print("Processing filename: %s" % filename)
    # If we're being asked to create a mezzanine file, we need to make a unique suffix for this file
    # but the suffix MUST be related to the file's contents, to be able to identify the file
    # so that we do not waste time encoding it twice. FFmpeg provides a hash function for this.
    # Incidentally, this might be a way of detecting duplicate tracks, too.
    if mezzanine:
        hashout = str(subprocess.check_output([FFMPEG, "-v", "quiet", "-hide_banner", "-i", filename, "-vn", \
                "-map", "0:a", "-f", "hash", "-hash", "MD5", "-"], stderr=subprocess.STDOUT))[6:-3]

        print("MD5 hash is: %s" % hashout)
        #randomString = ''.join(random.choice(string.ascii_letters) for i in range(6))
        baseName = os.path.splitext(os.path.basename(filename))[0] + "." + hashout + ".mka"
        mezzanineName = os.path.join(mezzanine, baseName)
        print("Mezzanine name is: %s" % mezzanineName)
        # Now we must detect if this file has already been converted
        # What we're interested in comparing is the string between the penultimate '.'
        # and the final '.'
        # Create a list with any filenames matching the hash.
        # If it contains an entry, the track has already been converted, and we
        # need to abandon the process.
        print("Looking for file containing hash.")
        p = Path(mezzanine+'/')
        findMe = mezzanine + '/' + '[FILENAME]' + hashout + '*.mka'
        print("Path object is:", p)
        print("Glob search is:", findMe)
        pl = list(p.glob('*'+hashout+'*.mka'))
        if len(pl) != 0: # There is already a file with this hash
            print("This hash already exists! Not encoding.")
            return(None)
        print("No file found with that hash. Encoding.")

    else:
        mezzanineName = None

    # We pass "-vn" because some music files have invalid images, which can't be processed by ffmpeg

    if mezzanine:
        test = str(subprocess.check_output([FFMPEG, "-hide_banner", "-i", filename, "-vn", "-af", \
                "ebur128", "-f", "null", "null"], stderr=subprocess.STDOUT)).split('\\n')
    else:
        test = str(subprocess.check_output([FFMPEG, "-hide_banner", "-y", "-i", filename, "-vn", "-af", "ebur128", "-f", "null", "null"], \
                stderr=subprocess.STDOUT)).split('\\n')
    measure = []
    #print(test[:-14])
    for item in test[:-12]:
        if  item.startswith("[Parsed_ebur128"):
            if item.find("Summary") == -1:
#                print(item, item[-86:-74], item[-53:-47])
                measure.append([float(item[-86:-74].strip()), float(item[-53:-47].strip())])

    # measure now contains a list of lists-of-floats: each item is [time],[loudness]
#   print("Testing THIS line for loudness: %s" % test[-9])
    loudness = float(test[-9].split()[1])

    # Get duration. It's the second item in the -13th line returned from
    # the FFmpeg process, in the list of lines named 'test'
    print("Stats line is %s" % test[-13])
    partiallyParsedDuration = test[-13].split("=")[2].split()[0]
    print("Duration line is %s" % partiallyParsedDuration)
    hmsSplit = partiallyParsedDuration.split(":")
    duration = float(int(hmsSplit[0])*3600 + int(hmsSplit[1])*60 + float(hmsSplit[2]))
    print("Duration is %f" % duration)
#    duration = float(measure[-1][0])
#    for item in measure:
#        print("time: %f, loudness: %f" % (item[0], item[1]))

    print("Overall loudness is: %f" % loudness)

    # First, let us find the first timestamp where the momentary loudness is volStart below the
    # track's overall loudness level. That level is cueLevel

    print("Desired start detection volume is %f" % volStart)
    cueLevel = loudness - volStart
    print("We're looking for %f LUFS volume." % cueLevel)
    # Set a sensible default if we can't find a start
    ebuCueTime=0.0

    for item in measure:
        if item[1] > cueLevel:
            ebuCueTime = item[0]
            break
    # The EBU R.128 algorithm measures in 400ms blocks. Therefore, it marks 0.4s as the
    # start of the track, even if its audio begins at 0.0s. So, we must subtract 400ms
    # from the given time, then use either that time, or 0.0s (if the result is negative)
    # as our track starting point.
    # We then take it back by a further 0.2s for safety -- NOT YET
    cueTime = max(0, ebuCueTime-0.4)

    print("Starting next track from cue point: %f" % cueTime)

    # Now we must find the last timestamp where the momentary loudness is volDrop LU below the track's
    # overall loudness level. That level is nextLevel.
    # We'll reverse the list
    measure.reverse()
    print("Desired volume lowering is %f" % volDrop)
    nextLevel = loudness - volDrop
    print("We're looking for %f LUFS volume." % nextLevel)
    # Set a sensible default if we can't find a drop
    nextTime=0.0

    for item in measure:
        if item[1] > nextLevel:
            nextTime = item[0]
            break
    print("Starting next track at time: %f which is %f before end." % (nextTime, duration-nextTime))
    # Little piece of logic to fix "Bohemian Rhapsody" and other songs with a long
    # but important tail.

    longTail = "False"

    if (duration-nextTime) > 15.0:
        longTail = "True"
        print("This track has a LONG TAIL.")
        print("Lowering next track trigger level by 15dB.")
        nextLevel = loudness - volDrop - 15.0
        print("We're looking for %f LUFS volume." % nextLevel)
        # Set a sensible default if we can't find the right drop
        nextTime = 0.0

        for item in measure:
            if item[1] > nextLevel:
                nextTime = item[0]
                break
        print("Starting next track at NEW time: %f which is %f before end." % (nextTime, duration-nextTime))

    # At this point, the file of interest is EITHER the original file, OR a mezzanine name.
    # ONLY IF we've made a mezzanine name, we want to add some metadata to show our working.
    if mezzanine:
        print("Creating mezzanine file with added metadata.")

        # Let's write the metadata, in case it's useful to somebody else
        # We need a temporary filename for FFmpeg to write to. We can't write metadata in place, because
        # the position of other elements in the file would change.
        temporaryFile = tempfile.NamedTemporaryFile(delete=False).name + ".mka"
        test = str(subprocess.check_output([FFMPEG, "-hide_banner", "-i", filename, \
                # "-vn", "-acodec", "libfdk_aac", "-vbr", "5", "-ar", "48000", "-ac", "2", \
                "-vn", "-acodec", "copy", \
                "-metadata:s:a:0", "longtail="+longTail, \
                "-metadata:s:a:0", "liq_cross_duration="+'{:.3f}'.format(max(duration-nextTime,0)), \
                "-metadata:s:a:0", "liq_cue_in="+'{:.3f}'.format(cueTime), \
                "-metadata:s:a:0", "duration="+'{:.3f}'.format(duration), \
                "-metadata:s:a:0", "loudness="+'{:.3f}'.format(loudness), temporaryFile], \
                stderr=subprocess.STDOUT)).split('\\n')
        os.rename(temporaryFile, mezzanineName)
    else:
        print("We are NOT adding metadata to any file.")

    return({"start_next": max(duration-nextTime,0), "cue_point": cueTime, "duration": duration, \
            "loudness": loudness, "mezzanine_name": mezzanineName,
            "longtail": longTail})

def fingerprint(filename):
    test = subprocess.check_output([FPCALC, "-algorithm", "4", "-overlap", "-length", "30", "-raw", "-plain", "-signed", filename], encoding='utf-8').rstrip('\n')
    return(test)


# What's the command?
parser = argparse.ArgumentParser(description="Create start and end-of-track annotations for playlist.",
        epilog="For support, contact john@johnwarburton.net")
parser.add_argument("playlist", help="Playlist file to be processed")
parser.add_argument("-l", "--level",  help="LU below average loudness to trigger next track.", default=8, type=float)
parser.add_argument("-c", "--cue", help="LU below average loudness for track cue-in point", default=40, type=float)
parser.add_argument("-o", "--output", help="Output filename (default: '-processed' suffix)", type=str)
parser.add_argument("-m", "--mezzanine", help="Directory for mezzanine-format files", type=str)
args = parser.parse_args()

playlist = args.playlist
level = float(args.level)
cue = float(args.cue)

# Construct default output filename if needed
if args.output:
    outfile = args.output
else:
    outfile = os.path.splitext(playlist)[0] + "-processed.m3u8"

# Check mezzanine directory name and create if needed
if args.mezzanine:
    # Convert given path to an absolute path
    mezzanine = os.path.abspath(args.mezzanine)
    try:
        os.makedirs(mezzanine, exist_ok=True)
        print("Created directory %s for output audio files." % mezzanine)
    except OSError:
        print("Sorry, the directory %s is weird. Might be a file?" % mezzanine)
        exit(1)
else:
    mezzanine = None

print("Working on playlist: %s" % playlist)
print("Looking for levels of %f LU below average loudness" % level)
print("Writing to %s" % outfile)

with open(playlist) as i:
    playlistLines = i.readlines()

print("We have read %s items." % len(playlistLines))

with open(outfile, mode="w") as out:
    out.write("#EXTM3U\n")

    for item in playlistLines:
        # Skip the M3U indicator
        if item == "#EXTM3U\n":
            continue
        result = analyse(filename=item.strip(), volDrop=level, volStart=cue, mezzanine=mezzanine, forceEncode=False)
        # analyse() returns None if the audio has already been converted.
        # At this point, we can skip writing a new line to the playlist, because the file is already
        # extant, and must have been referenced already within the playlist we're creating.
        if result==None:
            continue
        timeRemaining = result["start_next"]
        cuePoint = result["cue_point"]
        duration = result["duration"]
        # Here, we calculate replayGain by subtracting the actual loudness of the track from -23
        # because -23LUFS is our internal standard for loudness.
        # It's this low because many tracks have peaks way above their loudness level, and these
        # will distort if raised very far.
        replayGain = (-23) - result["loudness"]
        if result["mezzanine_name"]:
            # Remember, a file read in lines has a newline on the end of every line
            item = result["mezzanine_name"] + '\n'

        assembly = 'annotate:' + 'liq_cue_in="' + '{:.3f}'.format(cuePoint) \
                + '",' + 'liq_cross_duration="' + '{:.3f}'.format(timeRemaining) \
                + '",' + 'duration="' + '{:.3f}'.format(duration) \
                + '",' + 'liq_amplify="' + '{:.3f}'.format(replayGain) + "dB" \
                + '":' + item
        print("Writing line:")
        print(assembly)
        out.write(assembly)
        # Fingerprinting is now in a separate program
        #fing = fingerprint(item.strip())
        #fd = open('database.csv', 'a')
        #csvWriter = csv.writer(fd)
        #csvWriter.writerow([item.strip(), fing])
        #fd.close()
        #print("Fingerprint is:")
        #print(fing)
print("Done.")



