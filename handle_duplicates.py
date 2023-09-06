#!/usr/bin/python3

# Takes duplicates CSV file,
# plus original playlist m3u8 file,
# then:
# sorts CSV file by similarity (field 0)
# make a holding directory for audio
# open a new m3u8 file for possible duplicates
# for each line:
#   move file in field 1 to holding directory
#   move file in field 2 to holding directory

import csv
import argparse

parser = argparse.ArgumentParser(description='Separate out possible duplicates for manual checking.')
parser.add_argument('-d', '--duplicates', required=True, type=str, help='Filename of CSV with possible duplicates')
args = parser.parse_args()

duplicates = args.duplicates

# listofDupes will contain the duplicates, sorted with the best matches at the top
with open(duplicates, 'r') as csvfile:
    reader = csv.reader(csvfile)
    listofDupes = list(reader)

listofDupes.sort(key=lambda value: int(value[0]), reverse=True)
# print(listofDupes)

# We'd


