#!/usr/bin/python3

import os, ntpath, sys, pathlib, argparse



def convertfile(infile, mount):
    # Takes the DOS input filename including drive, and converts to Posix-style
    # together with the mount point added in place of the drive letter.

    # Tell the system what kind of path this is
    rawFile = pathlib.PureWindowsPath(infile)
    # Convert it to Python's Posix-style representation of a DOS pathname
    fileName=pathlib.PurePath.as_posix(rawFile)

    # Remove the drive letter, intelligently combine what's left with the mount point
#    print("Mount point is: %s" % mount)
    pathName=os.path.normpath(mount + '/' + ntpath.splitdrive(fileName)[1])

    return(pathName)




parser = argparse.ArgumentParser(description='Convert DOS/Windows playlist into Posix playlist.')
parser.add_argument('-i', '--infile', required=True, type=str, help='Filename of DOS/Windows playlist')
parser.add_argument('-o', '--outfile', required=True, type=str, help='Filename of output Posix-style playlist')
parser.add_argument('-r', '--root', required=True, type=str, help='Mount point of DOS/Windows drive letter')

args = parser.parse_args()

print(args)

infile = args.infile
outfile = args.outfile
root = args.root

with open(outfile, mode="w", encoding='utf-8') as outfp:
    with open(infile, encoding='utf-8-sig') as fp:
        for line in fp:
            intrack = line.strip()
    #        print(intrack)
            realtrack = convertfile(intrack, root)
            outfp.write(realtrack + '\n')

