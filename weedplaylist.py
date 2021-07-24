#!/usr/bin/python3
# Takes a playlist file, and a file with a list of files,
# moves the files in the list of files from the file location into a holding directory
# and cuts the playlist entry corresponding to that file, placing it into a new file.

import checkplaylist
import argparse
import json

parser = argparse.ArgumentParser(description='Removes files in a list of files from a liquidsoap m3u8 playlist,\n '
                                             'then moves them into a new subdirectory,\n '
                                             'then saves both a modified version of the given playlist having had \n'
                                             'the missing files cut out, and saves a new playlist with the missing files.')
parser.add_argument('inputfile', default=None, help='Filename of full m3u8 playlist to be weeded.')
parser.add_argument('filelist', default=None, help='Text file with list of files to be removed and optionally moved.')
parser.add_argument('--move', '-m', default=None, help='Actually move the file, instead of leaving them.')

args = parser.parse_args()

INPUTPLAYLIST = args.inputfile
FILESTOWEED = args.filelist
WEEDEDPLAYLIST = INPUTPLAYLIST + "_weeded.m3u8"
WEEDSPLAYLIST = INPUTPLAYLIST + "_weedsonly.m3u8"

# Need to make a list of all files that need to be weeded

with open(FILESTOWEED, 'r', encoding='utf-8') as fp:
    fileslist = [line.rstrip() for line in fp]

weededtuple = checkplaylist.weedplaylist(INPUTPLAYLIST, fileslist)
# Return is a tuple: (m3u8 of removed files, m3u8 of files remaining)

#print("REMOVED FILES:")
#print("\n".join(weededtuple[0]))
#print("RETURNED WEEDED PLAYLIST:")
#print(weededtuple[1].values())

with open(WEEDEDPLAYLIST, mode='w', encoding='utf-8') as wp:
    wp.write('#EXTM3U\n')
    wp.write('\n'.join(weededtuple[1]))

with open(WEEDSPLAYLIST, mode='w', encoding='utf=8') as wp:
    wp.write('#EXTM3U\n')
    wp.write('\n'.join(weededtuple[0]))

print("Weeded playlist is %s" % WEEDEDPLAYLIST)
print("Playlist of weeds is %s" % WEEDSPLAYLIST)



