#!/usr/local/bin/liquidsoap

# Make a log
#set("scheduler.fast_queues", 10)
#set("scheduler.generic_queues", 10)
#set("scheduler.non_blocking_queues", 10)
#set("scheduler.log", true)
set("log.file.path", "/tmp/basic-radio.log")
set("server.telnet", true)
set("server.telnet.bind_addr", "0.0.0.0")
set("server.telnet.port", 1234)
set("server.timeout", -1.0)
set("decoder.file_decoders", ["META","WAV","AIFF","MIDI","IMAGE","FFMPEG","FLAC","AAC","MP4","OGG","MAD"])
set("decoder.file_extensions.gstreamer", [])
set("decoder.mime_types.gstreamer", [])
set("decoder.file_extensions.ffmpeg",["mp3","mp4","m4a","wav","flac","ogg","webm","opus","mka"])
#set("protocol.external.curl", "/usr/bin/curl")
set("frame.audio.samplerate", 32000)
set("request.metadata_decoders.duration", false)
#set("ffmpeg.log.verbosity", "verbose")
#log_clocks(delay=1.0, interval=1.0, "/tmp/clocks.log")
# My function to break for news. Copied from
# fallback.skip, but made track sensitive
# THIS REALLY DOESN'T WORK YET. The
# incoming audio (from the playlist) doesn't fade out.
# But the fade-in of the next track works. Why?

def break.news(~input,f)
    def transition1(a,b) =
        b
    end
    def transition2(a,b) =
        add ([fade.initial(duration=0.01,type="exp",b), a])
    end
    fallback(track_sensitive=true,transitions=[transition1,transition2],[input,f])
end




security = single("/home/john/src/radio/fault.flac")

# Here's the playlist, cut as per our Python pre-production program dictates

myplaylist = amplify(override="liq_amplify", 1.0, cue_cut(playlist(length=60.0, "/home/john/src/radio/13Mar2018-processed-newmet.m3u8")))

# Now do the crossfades. Each track's end is determined by its fade-out
# given by the Python program, so they can overlap without clashing too much.
#

#myplaylist = break.news(input=request.queue(id="override"), myplaylist)

myplaylist = fallback(track_sensitive=true, [request.queue(id="override"), myplaylist])

#
#
#myplaylist = jwcross(myplaylist)
#
myplaylist = crossfade(fade_out=0.01, fade_in=0.01, default=(fun(a,b)->add(normalize=false,([b, a]))), conservative=true,  myplaylist)
#myplaylist = overlap_sources([myplaylist])

# Make the playlist secure

radio = fallback(track_sensitive = false, [myplaylist, security])

# Here, we use FFmpeg to process the audio, and convert it ready for transmission.
# It does not exit cleanly, for reasons I don't understand yet.
#
# We could use output.external, but metadata (e.g. what's playing) doesn't get transferred that way.
# The FFmpeg line is like a broadcast audio chain: we normalize the loudness over a few seconds
# then multi-band compress it, then add a single-band limiter before EBU R.128 normalization with a
# target of -14LUFS.
# The AAC stream is at about 38 kbit/s (variable), so should work almost everywhere.

output.icecast(description="Experimental stream using Liquidsoap", genre="Freeform", name="Music Too", host="127.0.0.1", port=8000, mount="audio.aac", public=true, url="http://warblefly.sytes.net:8000/audio.aac", timeout=240.0, format="audio/aac", password="REDACTED", %external(samplerate=32000, channels=2, process="ffmpeg -f s16le -ar 32000 -ac 2 -i pipe:0 -acodec libfdk_aac -vbr 1 -profile:a aac_he_v2 -vn -af dynaudnorm=g=7:m=70:r=1.0:c=1:b=1,asetnsamples=2048,volume=-18dB,mcompand='0.005\,0.1 6 -47/-40\,-34/-34\,-17/-33 100 | 0.003\,0.05 6 -47/-40\,-34/-34\,-17/-33 400 | 0.000625\,0.0125 6 -47/-40\,-34/-34\,-15/-33 1600 | 0.0001\,0.025 6 -47/-40\,-34/-34\,-31/-31\,-0/-30 6400 | 0\,0.025 6 -38/-31\,-28/-28\,-0/-25 15999',volume=+20dB,alimiter=limit=-4dB:asc=1,dynaudnorm=r=1.0:p=0.99:b=1:c=1 -f adts pipe:1"), radio)


output.icecast(description="Experimental stream using Liquidsoap (hifi)", genre="Freeform", name="Music Too", host="127.0.0.1", port=8000, mount="audio-hifi.aac", public=true,  url="http://warblefly.sytes.net:8000/audio-hifi.aac", timeout=240.0, format="audio/aac", password="REDACTED", %external(samplerate=32000, channels=2, process="ffmpeg -f s16le -ar 32000 -ac 2 -i pipe:0 -acodec libfdk_aac -vbr 5 -vn -af dynaudnorm=g=7:m=70:r=1.0 -f adts pipe:1"), radio)

output.icecast(description="Experimental stream using Liquidsoap (hifi-lowbw)", genre="Freeform", name="Music Too", host="127.0.0.1", port=8000, mount="audio-hifi-low.aac", public=true, url="http://warblefly.sytes.net:8000/audio-hifi-low.aac", timeout=240.0, format="audio/aac", password="REDACTED", %external(samplerate=32000, channels=2, process="ffmpeg -f s16le -ar 32000 -ac 2 -i pipe:0 -acodec libfdk_aac -vbr 1 -profile:a aac_he_v2 -vn -af dynaudnorm=g=7:m=70:r=1.0 -f adts pipe:1"), radio)

