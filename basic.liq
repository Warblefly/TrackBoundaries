#!/home/john/.opam/system/bin/liquidsoap

# Make a log
set("log.file.path", "/tmp/basic-radio.log")
set("server.telnet", true)
set("server.telnet.bind_addr", "127.0.0.1")
set("server.telnet.port", 1234)
set("server.timeout", -1.0)
set("decoder.file_extensions.ffmpeg",["mp3","mp4","m4a","wav","flac","ogg","webm"])
set("protocol.external.curl", "/usr/bin/curl")
set("ffmpeg.log.verbosity", "verbose")
set("protocol.process.inherit_env", false)

security = single("fault.flac")

# Here's the playlist, cut as per our Python pre-production program dictates

myplaylist = cue_cut(playlist(length=60.0, "YOUR_PLAYLIST"))

# Now do the crossfades. Each track's end is determined by its fade-out
# given by the Python program, so they can overlap without clashing too much.
#

# This is pending a working curl download mechanism. It's not yet used.
news=switch(
    track_sensitive=true,
        [(
            {18m}, (audio_to_stereo(single("http://johnwarburton.net/myfile.mp3")))
            
        )]
    )

#myplaylist = fallback.skip(input=news, myplaylist)
myplaylist = crossfade(fade_out=0.01, fade_in=0.01, conservative=false,  myplaylist)

# Make the playlist secure
#
radio = fallback(track_sensitive = false, [myplaylist, security])

# Here, we use FFmpeg to process the audio, and convert it ready for transmission.
# It does not exit cleanly, for reasons I don't understand yet.
#
# We could use output.external, but metadata (e.g. what's playing) doesn't get transferred that way.

output.icecast(description="Experimental stream using Liquidsoap", genre="Freeform", name="Music Too", host="127.0.0.1", port=8000, mount="audio.aac", format="audio/aac", password="YOUR_PASSWORD", %external(samplerate=44100, channels=2, process="ffmpeg -report -i pipe:0 -acodec libfdk_aac -vbr 2 -profile:a aac_he_v2 -vn -af dynaudnorm=g=13,asetnsamples=2048,mcompand='0.000\,0.5 6 -20/-20\,0/-12 150 | 0.000\,0.3 6 -20/-20\,0/-12 3300 | 0.000\,0.07 6 -20/-20\,0/-12 22000',volume=+10dB,alimiter=-4dB -f adts pipe:1"), radio)

