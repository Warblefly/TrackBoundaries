#!/usr/bin/python3

### Dedup.py
###
### (C) John Warburton 2020
###
### Iterate through all combinations in a list of chromaprints,
### detect and print near matches.
### This helps eliminate tracks in a playlist that contain similar audio
###
### Uses parallel processing. Redirect output to get a list for working on.
###


import itertools
from fuzzywuzzy import fuzz
from multiprocessing import Pool
from multiprocessing import cpu_count
import csv, sys

CPUCOUNT = cpu_count()
# This is the filename of the .csv containing the chromaprints to compare
FILENAME = 'chromaprints.csv'

with open(FILENAME) as csvfile:
    DATA = list(csv.reader(csvfile))

DATALENGTH = len(DATA)

print("We will use %s processes." % CPUCOUNT, file=sys.stderr)
print("We have read %s lines." % DATALENGTH, file=sys.stderr)
print("Starting to make list of combinations...", file=sys.stderr)
combos = list(itertools.combinations(range(0, DATALENGTH), 2))
print("There are %s combinations to explore." % len(combos), file=sys.stderr)
print("*** DATABASE", file=sys.stderr)


def checkcombo(tracklistCombos):
    # print("Matching: ", tracklistCombos)
    match = fuzz.ratio(DATA[tracklistCombos[0]][1], DATA[tracklistCombos[1]][1])
#    if (match >= 50):
        #print("We're matching %s with %s." % (DATA[tracklistCombos[0]][1], DATA[tracklistCombos[1]][1]))
        #print("Closeness of %s is %s" % (tracklistCombos, match))
        #print("This represents:")
        #print(DATA[tracklistCombos[0]][0])
        #print("and")
        #print(DATA[tracklistCombos[1]][0])i
        #print("%s, %s, %s" % (match, DATA[tracklistCombos[0]][0], DATA[tracklistCombos[1]][0]))
#        print('%s, "%s", "%s"' % (match, DATA[tracklistCombos[0]][0].replace('"', '""'), DATA[tracklistCombos[1]][0].replace('"', '""')))
    if (match >= 71):
        # Check durations. Are the tracks within 10s of each other?
        difference = abs(float(DATA[tracklistCombos[0]][2]) - float(DATA[tracklistCombos[1]][2])) 
        print("Match found: difference is %s" % difference, file=sys.stderr)
        if difference <= 10:
            print('%s, "%s", "%s"' % (match, DATA[tracklistCombos[0]][0].replace('"', '""'), DATA[tracklistCombos[1]][0].replace('"', '""')))
        

def pool_handler():
    p = Pool(CPUCOUNT)
    p.map(checkcombo, combos)


if __name__ == '__main__':
    pool_handler()



#for check in combos:
#    match = fuzz.ratio(data[check[0]], data[check[1]])
#    if (match >= 60):
#        print("Closeness of %s is %s" % (check, match))
#        print("This represents:")
#        print(data[check[0]][0])
#        print("and")
#        print(data[check[1]][0])



