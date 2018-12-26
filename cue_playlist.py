#!/usr/bin/python3

import subprocess, argparse, os.path

FFMPEG = "/usr/local/bin/ffmpeg"

def analyse(filename, volDrop=11):
    # Analyses file in filename, returns seconds to end-of-file of place where volume last drops to level
    # below average loudness, given in volDrop in LU.

    # Make a list containing many points, 1/10 sec apart, where loudness is measured.
    # We need TIME and MOMENTARY LOUDNESS
    # We also need full INTEGRATED LOUDNESS

    print("Processing filename: %s" % filename)
    # We pass "-vn" because some music files have invalid images, which can't be processed by ffmpeg

    test = str(subprocess.check_output([FFMPEG, "-hide_banner", "-i", filename, "-vn", "-af", "ebur128", "-f", "null", "null"], \
            stderr=subprocess.STDOUT)).split('\\n')
    measure = []

    # Here, we spot the figures we need, in the wider FFmpeg EBU R.128 output
    
    for item in test[:-14]:
        if  item.startswith("[Parsed_ebur128"):
            #print(item, item[-86:-74], item[-53:-47])
            measure.append([float(item[-86:-74].strip()), float(item[-53:-47].strip())])

    # measure now contains a list of lists-of-floats: each item is [[time],[loudness]]

    # This data, at the end of FFmpeg's output, also contains audio duration.
    loudness = float(test[-9].split()[1])
    duration = float(measure[-1][0])
#    for item in measure:
#        print("time: %f, loudness: %f" % (item[0], item[1]))

    print("Overall loudness is: %f" % loudness)

    # Now we must find the last timestamp where the instantaneous loudness is volDrop LU below the track's
    # overall loudness level. That level is nextLevel.
    # We'll reverse the list
    measure.reverse()
    print("Desired volume lowering is %f" % volDrop)
    nextLevel = loudness - volDrop
    print("We're looking for %f LUFS volume." % nextLevel)
    nextTime=0.0

    for item in measure:
        if item[1] > nextLevel:
            nextTime = item[0]
            break

    print("Starting next track at time: %f which is %f before end." % (nextTime, duration-nextTime))
    return(duration-nextTime)

# What's the command?
parser = argparse.ArgumentParser(description="Create end-of-track annotation for playlist.")
parser.add_argument("playlist", help="Playlist file to be processed")
parser.add_argument("-l", "--level",  help="LU below average loudness to trigger next track.", default=11)
parser.add_argument("-o", "--output", help="Output filename (default: '-proc' suffix)")
args = parser.parse_args()

playlist = args.playlist
level = float(args.level)

# Construct default output filename if needed
if args.output:
    outfile = args.output
else:
    outfile = os.path.splitext(playlist)[0] + "-processed.m3u8"

print("Working on playlist: %s" % playlist)
print("Looking for levels of %f LU below average loudness" % level)
print("Writing to %s" % outfile)

with open(playlist) as i:
    playlistLines = i.readlines()

print("We have read %s items." % len(playlistLines))

with open(outfile, mode="w") as out:
    
    # Create a new playlist file, with the liquidsoap "annotate" protocol showing where to
    # start the next track, for each track in the playlist
    
    for item in playlistLines:
        timeRemaining = analyse(item.strip(), level)
        assembly = 'annotate:' + 'liq_start_next="' + '{:.1f}'.format(timeRemaining) + '":' + item
        print("Writing line:")
        print(assembly)
        out.write(assembly)
print("Done.")
