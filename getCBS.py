#!/usr/bin/python3
# Program to retrieve the latest CBS radio news as a file.
# The news URL changes hourly, but it is easy to work out:
# 27May2019 - changed timezone to Central. Since May 20th,
# bulletins have stepped back by an hour, and I don't
# know why.


import datetime, pytz
#, wget

PREFIX = "http://audio.cbsradionewsfeed.com/"
#RAW_DL = "CBS_raw.mp3"
#PART1_AUDIO = "CBS_part1.wav"
#PART2_AUDIO = "CBS_part2.wav"
#PART2_AUDIO_CUT = "CBS_part2-cut.wav"
#CBS_EDITED = "CBS_news.mka"

# Time, in seconds, where we start to look for the silence marking the end of bulletin.

#SPLIT = 240


est = datetime.datetime.now(pytz.timezone('US/Eastern'))

year = str(est.year)
month = "{:02}".format(est.month)
date = "{:02}".format(est.day)
hour = "{:02}".format(est.hour)

URL = year + '/' + month + '/' + date + '/' + hour + '/Hourly-' + hour + '.mp3'

# We need to get this URL, divide it into two, and search for the first silence in the second part.

print(PREFIX + URL)


