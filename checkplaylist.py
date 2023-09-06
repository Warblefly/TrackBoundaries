#!/usr/bin/python3
# This is a MODULE

import os
import argparse
import tempfile


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

def findhash(inputfilename: str):
    # Takes a filename, returns the hash contained within it
    return inputfilename.split('.')[-2]


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

def weedplaylist(playlist: str, filelist: list):
    # Function to remove lines from a playlist, and drop their associated files into a temporary directory
    # We need a temporary directory to drop files into
    tempdir = tempfile.mkdtemp(suffix=None, prefix='moved_files_', dir='.')
    print(f"Moving files into {tempdir}.")
    # Remember: this is a playlist which is used for liquidsoap, so is not merely a list of
    # filenames -- it has annotations, too.
    # From the playlist, we must make a list of lists:
    # [0] = entry annotation without filename
    # [1] = filename alone
    # then place each of these lists in a dictionary, indexed by the hash alone.
    workingdictionary = dict()
    removedlist = []
    with open(playlist, 'r', encoding='utf-8') as pl:
        for line in pl:
            # print("Checking playlist" % pl)
            workingentry = ['', '']
            # We do a try / except because the first line is an "#EXTM3U"
            try:
                workingentry[0], workingentry[1] = line.rsplit(":",1)
                # Beware! At this point, workingentry[1] has a \n at its end.
                workingentry[1] = workingentry[1].strip()
            except:
                continue
            workingdictionary[findhash(workingentry[1])] = workingentry
            # print("workingdictionary is" % workingdictionary)
    #print(workingdirectory)
    # Now to step through the list of files.
    # It doesn't matter if these are full pathnames or just filenames
    # It's only the hash that matters.
    for filetoremove in filelist:
        # Retrieve the filename as shown in the playlist, which may be its full path
        hash = findhash(filetoremove)
        playlistentry = workingdictionary[hash]
        # Move the file by its full path into the subdirectory we have chosen
        newpathname = os.path.join(tempdir, os.path.basename(playlistentry[1]))
        print(f"Renaming {playlistentry[1]} to {newpathname}")
        os.rename(playlistentry[1], newpathname)
        # Now remove this line from the workingdictionary, and put it into removeddictionary
        # so that we have a new playlist consisting of the moved files; and an old playlist
        # with the removed files missing.
        removedlist.append(playlistentry[0] + ':' + os.path.join(os.getcwd(), newpathname))
        workingdictionary.pop(hash)

    # Now, convert the workingdictionary back from the annotation : filename notation
    # to a proper playlist entry.

    weededplaylist = []

    for entry in workingdictionary.values():
        weededplaylist.append(entry[0] + ":" + entry[1])


    return(removedlist, weededplaylist)
