#!/usr/bin/python3

import os
import argparse
import xml.etree.ElementTree as ET
import subprocess
import os.path
import string

def filePrefix(filename, hash=True):
    # Hash is the hash that the "Music Too" playlist system creates
    # to identify uniquely a file. We don't need to consider it when
    # trying to determine the tags for a file.
    splitPos = 1 if hash==False else 2
    splitFront = filename.rsplit('.', splitPos)[0]
    return os.path.basename(splitFront)

def getMetadata(filename):
    # Metadata for title and artist can appear in at least two places in the file.
    # Returns False if there's nothing to use, returns a dictionary with data if there is.
    # Some of it might be in the container,
    # while some might be in the stream within the container.
    # We should check both.
    # First, get the tags.
    title = None
    artist = None
    output = subprocess.check_output(['ffprobe', '-loglevel', 'quiet', "-hide_banner", "-of", "xml", '-show_entries', \
            'format_tags:stream_tags', filename], \
            stderr=subprocess.STDOUT)
    # We'll dig down into 'output', which is XML, and locate the first instance of meaningful fields for
    # 'artist' and 'title'
    xml = ET.fromstring(output)
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
        artist = xml.find(".//tag[@key='Title']").attrib['value']
    except AttributeError:
        pass
    try:
        artist = xml.find(".//tag[@key='title']").attrib['value']
    except AttributeError:
        pass

    return{'artist': artist, 'title': title}

def removeEndNumber(filename, limit=4):
    clean = filename.rstrip(string.digits)
    if len(clean) <= len(filename)-limit:
        return clean
    else:
        return filename

def removeFrontNumber(filename, limit=1):
    clean = filename.lstrip(string.digits)
    print("DEBUG: clean is %s, filename is %s" % (clean, filename))
    if len(clean) <= len(filename)-limit:
        return clean
    else:
        return filename

def removeEndPunctuation(filename):
    # We don't use string.punctuation because brackets are often part of a song title
    return filename.rstrip("!\"#$%&*+.,-/:;<=>?@\^_`|~ ")

def removeFrontPunctuation(filename):
    return filename.lstrip("!\"#$%&*+.,-/:;<=>?@\^_`|~ ")

def generateMetadata(filename):
    # If there's a number at the end AND it has more than four digits, discard it and any punctuation preceding itself.
    # If there's a number at the front, discard it AND ANY PUNCTUATION THAT FOLLOWS IT
    # If there's still a number at the end and it has more th an four digits, discard it and any punctuation preceding itself.
    # If there's still a number at the front, discard it and any following punctuationself.
    # Replace all "_" with " "
    # Look for the last "-". If there's a "-", split the string around the last one.
    # Discard any whitespace around what's left.
    # The first piece is the artist, the second is the title.

    # Take a number off the end if it has more than 4 digits
    mod1 = removeEndNumber(filename)
    # Remove any puncutation before that
    mod2 = removeEndPunctuation(mod1)
    # Remove any large number still remaining in case there was a hyphen in the middle of a catalogue number
    mod3 = removeEndNumber(mod2)
    # Remove any punctuation remaining here
    mod4 = removeEndPunctuation(mod3)

    # Take a number off the front (e.g. a track number)
    mod5 = removeFrontNumber(mod4)
    # Remove punctuation after that
    mod6 = removeFrontPunctuation(mod5)
    # Remove any remaining number after that
    mod7 = removeFrontNumber(mod6)
    # Remove any remaining punctuation
    mod8 = removeFrontPunctuation(mod7)

    # Replace any underscores with spaces
    mod9 = mod8.replace("_", " ")

    # Find the last hyphen and split the string at that point
    unstrippedTitleList = mod9.rsplit("-", 1)
    titleList = [item.strip() for item in unstrippedTitleList]
    cappedTitleList = [string.capwords(item) for item in titleList]
    if len(cappedTitleList) < 2:
        cappedTitleList.append(None)
    # Usually, the artist is first, the title second

    return(cappedTitleList[0], cappedTitleList[1])
