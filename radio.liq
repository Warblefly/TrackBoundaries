#!/home/[USERNAME]/.opam/system/bin/liquidsoap

# Make a log
set("log.file.path", "/tmp/radio-liq.log")
set("server.telnet", true)
set("server.telnet.bind_addr", "127.0.0.1")
set("server.telnet.port", 1234)
set("server.timeout", -1.0)
set("decoder.file_extensions.ffmpeg",["mp3","mp4","m4a","wav","flac","ogg","webm"])

security = single("fault.flac")

# Here's the playlist, cut as per our Python pre-production program dictates

myplaylist = cue_cut(playlist(length=60.0, "[YOURPLAYLIST]"))

# Now do the crossfades. Each track's end is determined by its fade-out
# given by the Python program, so they can overlap without clashing too much.

myplaylist = crossfade(fade_out=0.01, fade_in=0.01, conservative=false,  myplaylist)

# Make the playlist secure

radio = fallback(track_sensitive = false, [myplaylist, security])

# Here, we use FFmpeg to process the audio, and convert it ready for transmission.
# The built-in fdkaac encoder, for reasons I don't understand yet, distorts when using AAC HE v2 encoding only.
# It does not exit cleanly, for reasons I don't understand yet.
#
# We could use output.external, but metadata (e.g. what's playing) doesn't get transferred that way.

output.icecast(host="[YOURHOST]", port=8000, mount="audio.aac", format="audio/aac", password="[YOURPASSWORD]", %external(samplerate=44100, channels=2, process="ffmpeg -report -i pipe:0 -acodec libfdk_aac -vbr 1 -profile:a aac_he_v2 -vn -af dynaudnorm,alimiter=level_in=+5dB:limit=-1dB:level=1:asc=1 -f adts pipe:1"), radio)
