#!/usr/bin/python3

import os
import argparse
import xml.etree.ElementTree as ET
import subprocess
import os.path
import string
import glob
import tempfile

# The version number gets embedded as metadata in the field "missingmetadata"
# so we know not to touch data created by later versions, in case someone
# runs an old script.
VERSION="0.2"
FFMPEG="ffmpeg"

def filePrefix(filename, containsHash=True):
    # Hash is the hash that the "Music Too" playlist system creates
    # to identify uniquely a file. We don't need to consider it when
    # trying to determine the tags for a file.
    splitPos = 1 if containsHash==False else 2
    splitFront = filename.rsplit('.', splitPos)[0]
    return os.path.basename(splitFront)

def replaceMetadata(filename=None, artist="", title=""):

    artist = "" if artist is None else artist
    title = "" if title is None else title

    # Get a temporary filename for storing output
    fileExtension = os.path.splitext(filename)[1]
    tempFile = tempfile.NamedTemporaryFile(delete=False).name + fileExtension
    print("replaceMetadata has received filename %s, artist %s, title %s" % (filename, artist, title))

    try:
        output = subprocess.check_output([FFMPEG, '-i', filename, '-c', 'copy', '-metadata', 'title=' + title, \
            '-metadata', 'artist=' + artist, '-metadata', 'MISSINGMETADATAVERSION=' + VERSION, '-vn', tempFile], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        print("File %s caused FFmpeg error. Is it an audio file?" % filename)
        return False


    print("Output was %s" % output.decode("utf-8"))
    print("Incoming filename was %s", filename)
    print("Temporary filename was %s", tempFile)

    os.replace(tempFile, filename)

def getMetadata(filename):
    # Metadata for title and artist can appear in at least two places in the file.
    # Returns False if there's nothing to use, returns a dictionary with data if there is.
    # Some of it might be in the container,
    # while some might be in the stream within the container.
    # We should check both.
    # First, get the tags.
    title = None
    artist = None
    retrievedVersion = None
    handler = None
    try:
        output = subprocess.check_output(['ffprobe', '-loglevel', 'quiet', "-hide_banner", "-of", "xml", '-show_entries', \
            'format_tags:stream_tags', filename], \
            stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        print("File %s might not be an audio file." % filename)
        return False

    # We'll dig down into 'output', which is XML, and locate the first instance of meaningful fields for
    # 'artist' and 'title'
    xml = ET.fromstring(output)
    # Importantly, we look for the signature that this data has ALREADY been created by this program.
    # If it has, AND it's by a later version, don't touch it


    # The first test tries to retrieve the version number of any previous instance of this
    # script that has modified the file's metadata
    try:
        retrivedVersion = xml.find(".//tag[@key='MISSINGMETADATAVERSION']").attrib['value']
    except AttributeError:
        pass

    # We can't search in a case-insensitive way, so we have to do this the hard way.
    try:
        artist = xml.find(".//tag[@key='ARTIST']").attrib['value']
    except AttributeError:
        pass
    try:
        artist = xml.find(".//tag[@key='Artist']").attrib['value']
    except AttributeError:
        pass
    try:
        artist = xml.find(".//tag[@key='artist']").attrib['value']
    except AttributeError:
        pass

    try:
        title = xml.find(".//tag[@key='TITLE']").attrib['value']
    except AttributeError:
        pass
    try:
        title = xml.find(".//tag[@key='Title']").attrib['value']
    except AttributeError:
        pass
    try:
        title = xml.find(".//tag[@key='title']").attrib['value']
    except AttributeError:
        pass

    try:
        handler = xml.find(".//tag[@key='HANDLER_NAME']").attrib['value']
    except AttributeError:
        pass

    return{'artist': artist, 'title': title, 'version': retrievedVersion, 'handler': handler}

def removeEndNumber(filename, limit=4):
    clean = filename.rstrip(string.digits)
    if len(clean) <= len(filename)-limit:
        return clean
    else:
        return filename

def removeFrontNumber(filename, limit=1):
    clean = filename.lstrip(string.digits)
#    print("DEBUG: clean is %s, filename is %s" % (clean, filename))
    if len(clean) <= len(filename)-limit:
        return clean
    else:
        return filename

def removeYouTubeSuffix(filename, handler=None):
    # Is this a YouTube file (indicated by 'handler')
    # AND is there a sequence of between 6 and 12 alphanumeric characters preceded by a
    # '-', and NO SPACES from the hyphen to the end of the string?
    if handler:
        if ('Google' in handler) or ('SoundHandler' in handler):
            print("This is a YouTube file: %s" % filename)
            test = filename.rsplit("-", 1)
            # If this is a list, we've found a hyphen
            if type(test) is list:
                print("Split to: %s" % str(test))
                suffix = test[-1]
                # There may be underscores in here. Don't want them.
                suffix = suffix.replace('_', '')
                if (suffix.isalnum() and (6 <= len(suffix) <= 15)):
                    clean = test[0]
                    print("We've changed it to %s" % clean)
                    return clean
                else:
                    return filename
            else:
                return filename
        else:
            return filename
    else:
        return filename

def removeEndPunctuation(filename):
    # We don't use string.punctuation because brackets are often part of a song title
    return filename.rstrip("\"#$%&*+.,-/:;<=>@\^_`|~ ")

def removeFrontPunctuation(filename):
    return filename.lstrip("\"#$%&*+.,-/:;<=>@\^_`|~ ")

def sanitizeString(filename, handler=None):
    # If there's a number at the end AND it has more than four digits, discard it and any punctuation preceding itself.
    # If there's a number at the front, discard it AND ANY PUNCTUATION THAT FOLLOWS IT
    # If there's still a number at the end and it has more th an four digits, discard it and any punctuation preceding itself.
    # If there's still a number at the front, discard it and any following punctuationself.
    # Replace all "_" with " "
    # Look for the last "-". If there's a "-", split the string around the last one.
    # Discard any whitespace around what's left.
    # The first piece is the artist, the second is the title.
    # NB There MUST be a way of doing this with an extended regular expression!!
    # It would be way more efficient.

    # Take a number off the end if it has more than 4 digits
    mod1 = removeEndNumber(filename)
    # Remove any puncutation before that
    mod2 = removeEndPunctuation(mod1)
    # Remove any large number still remaining in case there was a hyphen in the middle of a catalogue number
    mod3 = removeEndNumber(mod2)
    # Remove any punctuation remaining here
    mod4 = removeEndPunctuation(mod3)
    # Remove YouTube suffix
    #print("Calling removeYouTubeSuffix with %s, %s" % (mod4, handler))
    mod4a = removeYouTubeSuffix(mod4, handler)
    #print(mod4a)
    # Take a number off the front (e.g. a track number)
    mod5 = removeFrontNumber(mod4a)
    # Remove punctuation after that
    mod6 = removeFrontPunctuation(mod5)
    # Remove any remaining number after that
    mod7 = removeFrontNumber(mod6)
    # Remove any remaining punctuation
    mod8 = removeFrontPunctuation(mod7)

    # Replace any underscores with spaces
    mod9 = mod8.replace("_", " ")
    return mod9

def generateMetadata(filename, handler=None):
    sanitized = sanitizeString(filename, handler)

    # Find the last hyphen and split the string at that point
    unstrippedTitleList = sanitized.rsplit("-", 1)
    titleList = [item.strip() for item in unstrippedTitleList]
    cappedTitleList = [string.capwords(item) for item in titleList]
    # Each word in the list might have numbers or unwanted punctuation. Remove this.
    sanitizedCappedTitleList = [sanitizeString(item) for item in cappedTitleList]
    if len(sanitizedCappedTitleList) < 2:
        sanitizedCappedTitleList.append(None)
    # Usually, the artist is first, the title second

    return(sanitizedCappedTitleList[0], sanitizedCappedTitleList[1])

def makeFilenameList(pattern):
    return glob.glob(pattern)


# The business.

parser = argparse.ArgumentParser(description='Fill in missing metadata for media file, derived from filename.')
parser.add_argument('pattern', nargs='*', help='Filename(s) to examine or modify. Shell wildcards accepted.')
parser.add_argument('-m', action='store_true', help='Insert new metadata if none exists (default is to leave alone).')
parser.add_argument('-f', action='store_true', help='Force replacement of metadata even if this should not normally be done.')
parser.add_argument('-u', action='store_true', help='Disregard unique hash before file extension.')

args = parser.parse_args()

PATTERN = args.pattern
INSERT = args.m
FORCE = args.f
HASH = args.u

skipHash = True if HASH == True else False

#print("Pattern is %s, insert is %s, force is %s" % (PATTERN, INSERT, FORCE))

filesTotal = len(PATTERN)
print("Preparing to process %s files..." % filesTotal)

count = 0

for filename in PATTERN:
    count += 1
    print("Processing file %s of %s" % (count, filesTotal))
    alreadyMetadata = getMetadata(filename)
    if alreadyMetadata == False:
        continue
    if ((alreadyMetadata['version'] == None) or (float(alreadyMetadata['version']) < VERSION)) or (FORCE == True):
        #print("Processing: %s" % filename)
        # What's the important part of the filename we need to inspect?
        prefix = filePrefix(filename, skipHash)
        # Do we have either a title or an artist?
        if (alreadyMetadata['title'] != None) or (alreadyMetadata['artist'] != None):
        #    print("No new metadata for %s" % filename)
            continue
        else:
            if INSERT == True:
                # Remember that 'hander' indicates whether YouTube processed this file
                print("Calling generateMetadata on %s, %s" % (prefix, alreadyMetadata['handler']))
                newMetadata = generateMetadata(prefix, alreadyMetadata['handler'])
                print("For filename %s: " % filename)
                print("Using metadata %s" % str(newMetadata))
                print("Contained metadata %s" % str(alreadyMetadata))
                replaceMetadata(filename, artist=newMetadata[0], title=newMetadata[1])
            else:
                print("Instructed not to add metadata to %s" % filename)
    else:
        print("Skipping: %s" % filename)



