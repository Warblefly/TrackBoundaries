#!/usr/bin/python3

import subprocess, argparse, os, os.path, random, string, tempfile, csv, re, shutil
from pathlib import Path

FFMPEG = "/usr/local/bin/ffmpeg"
MEZZANINE = "-acodec libfdk_aac -vbr 5 -ac 2 -map 0:a"
MD5HashRE = re.compile(r'(?i)(?<![a-z0-9])[a-f0-9]{32}(?![a-z0-9])')

def analyse(filename, mezzanine=None, forceEncode=False):
    # Encode and store a mezzanine file, if a mezzanine directory name is given

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

        # But! If this filename already contains a hash, we need to remove it before adding this one.
        # A hash exists in the between the second-to-last . and the last .
        # and has 32 characters from 0-9,a-f

        origBaseName = os.path.basename(filename)
        searchCheck = re.search(MD5HashRE, origBaseName)
        print("Debug: searchcheck = %s" % searchCheck)

        if searchCheck:
            # Remove the existing hash
            # No action required if there isn't any hash in the first place
            baseNameNoHash = origBaseName.replace('.' + searchCheck.group(0), '')
            print("Debug: name without hash: %s" % baseNameNoHash)
            origBaseName = baseNameNoHash


        baseName = os.path.splitext(origBaseName)[0] + "." + hashout + ".mka"
        print("Debug: name with replaced hash: %s" % baseName)

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

    # At this point, the file of interest is EITHER the original file, OR a mezzanine name.
    if mezzanine:
        print("Creating mezzanine file.")

#        # We need a temporary filename for FFmpeg to write to. We can't write metadata in place, because
#        # the position of other elements in the file would change.
#        temporaryFile = tempfile.NamedTemporaryFile(delete=False).name + ".mka"
#        test = str(subprocess.check_output([FFMPEG, "-hide_banner", "-i", filename, \
#                "-vn", "-acodec", "copy", temporaryFile], stderr=subprocess.STDOUT)).split('\\n')
#        shutil.move(temporaryFile, mezzanineName)
#    else:
#        print("We are NOT creating a new file.")
#

        if mezzanineName == filename:
            # No! FFmpeg can do bad things if replacing a file in-place
            raise ValueError("mezzanineName must be different from filename!")

        dest_dir = os.path.dirname(mezzanineName) or "."

        if not os.path.isdir(dest_dir):
            raise FileNotFoundError(f"Destination directory does not exist: {dest_dir}")

        print("Creating mezzanine file.")

        cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
               "-i", filename,
               "-map", "0:a",
               "-c", "copy",
               "-map_metadata", "0",
               "-map_metadata:s:a", "0:s:a",
               "-map_chapters", "-1",
               mezzanineName]
        print("debug: CMD is %s" % cmd)
        rc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("debug: returned from FFmpeg")

        if rc.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {rc.stderr.decode(errors='ignore')}")
        print("Mezzanine created at:", mezzanineName)
    return({"mezzanine_name": mezzanineName})


# What's the command?
parser = argparse.ArgumentParser(description="Create start and end-of-track annotations for playlist.",
        epilog="For support, contact john@johnwarburton.net")
parser.add_argument("playlist", help="Playlist file to be processed")
parser.add_argument("-o", "--output", help="Output filename (default: '-processed' suffix)", type=str)
parser.add_argument("-m", "--mezzanine", help="Directory for mezzanine-format files", type=str)
args = parser.parse_args()

playlist = args.playlist

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
        result = analyse(filename=item.strip(), mezzanine=mezzanine, forceEncode=False)
        # analyse() returns None if the audio has already been converted.
        # At this point, we can skip writing a new line to the playlist, because the file is already
        # extant, and must have been referenced already within the playlist we're creating.
        if result==None:
            continue
        if result["mezzanine_name"]:
            # Remember, a file read in lines has a newline on the end of every line
            item = result["mezzanine_name"] + '\n'

        assembly  = item
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
