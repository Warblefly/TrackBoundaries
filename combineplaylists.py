#!/usr/bin/python3

import argparse
import fnmatch
import os

def removeextinf(inputlist):
    PATTERN = '#*'
    matcheslist = fnmatch.filter(inputlist, PATTERN)
    return [x for x in inputlist if x not in matcheslist]

def removeduplicates(mylist):
    return list(set(mylist))


parser = argparse.ArgumentParser(description='Combine several playlists.')
parser.add_argument('-i', '--infile', required=True, action='append', type=str, help='Filename of playlist. Can be given multiple times.')
parser.add_argument('-o', '--outfile', required=True, type=str, help='Filename of output playlist')
parser.add_argument('-d', '--allowduplicates', action='store_true', help='Allow duplicate entries in output playlist.')

args = parser.parse_args()

print(args)

infilelist = args.infile
outfile = args.outfile
allowduplicates = args.allowduplicates

if os.path.exists(outfile):
    print(f'Sorry, the output file {outfile} already exists. Stopping right there.')
    exit(1)

# Create a list with all the lists combined
newplaylist = []

for infile in infilelist:
    with open(infile, mode='r', encoding='utf-8-sig') as fp:
        newplaylist.extend(removeextinf(fp.readlines()))

# Now remove duplicates
if not allowduplicates:
    newplaylist = removeduplicates(newplaylist)
else:
    pass

with open(outfile, mode="w", encoding='utf-8') as outfp:
    outfp.write("#EXTM3U\n")
    outfp.writelines(newplaylist)

print(f'Complete playlist written to {outfile}.')

