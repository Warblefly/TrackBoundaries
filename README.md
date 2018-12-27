# TrackEndDetect
Automatically detects the boundary between silence and the start of an audio track. Also, detects audio fade out, and notates a liquidaudio playlist accordingly, with both cue points.

Detection is based on a certain level of Loudness Units (LU) below the track's measured integrated loudness, according to EBU R.128 calculations. This is no mere "meter reader".

The fine multimedia automation software liquidsoap, which is the backbone of several user-friendly radio production operations, allows crossfading between sources.

However, it does not automatically fire the next item in a playlist based on a detected end of track; it instead relies on human interaction (or the end of a file) to point out where that end might be. 

There is a "smart" crossfade operator that looks at how tracks end and begin, to attempt to decide how to blend two tracks together, but it does not detect exactly when to do it.

This Python3 script parses a playlist, uses the EBU R.128 loudness measurement algorithm to determine the last point in an audio file where the loudness falls below a set level (e.g. the song's fade-out, or its end), and supplies metadata that liquidsoap can use to fire the next item in a playlist.

It is currently in test, but works. Run the command with '-h' to get help, or read the source.
