#!~/.opam/system/bin/liquidsoap

# Make a log
set("scheduler.fast_queues", 2)
set("scheduler.generic_queues", 5)
set("scheduler.non_blocking_queues", 4)
set("scheduler.log", true)
set("log.file.path", "/tmp/basic-radio.log")
set("server.telnet", true)
set("server.telnet.bind_addr", "127.0.0.1")
set("server.telnet.port", 1234)
set("server.timeout", -1.0)
set("decoder.file_extensions.ffmpeg",["mp3","mp4","m4a","wav","flac","ogg","webm","opus","mka"])
set("protocol.external.curl", "/usr/bin/curl")
set("frame.audio.samplerate", 32000)
set("request.metadata_decoders.duration", false)
#set("ffmpeg.log.verbosity", "verbose")


# My function to break for news. Copied from
# fallback.skip, but made track sensitive
# THIS REALLY DOESN'T WORK YET. The
# incoming audio (from the playlist) doesn't fade out.
# But the fade-in of the next track works. Why?

def break.news(~input,f)
    def transition1(a,b) =
        #source.skip(a)
        # This eats the last remaining frame from a
        #smooth_add(p=0.0,normal=a,special=b)
        #add ([b, fade.final(duration=2.0,type="log",a)])
        #sequence([fade.final(duration=2.0,type="log", a), b])
        #source.skip(a)
        b
    end
    def transition2(a,b) =
        #source.skip(b)
        add ([fade.initial(duration=0.01,type="exp",b), a])
    end
    fallback(track_sensitive=true,transitions=[transition1,transition2],[input,f])
end


security = single("/home/john/src/radio/fault.flac")

# Here's the playlist, cut as per our Python pre-production program dictates

myplaylist = amplify(override="liq_amplify", 1.0, cue_cut(playlist(length=60.0, "/home/john/src/radio/B2-mod.m3u8")))

# Inject news bulletins collected via crontab, inserted by an expect script

myplaylist = break.news(input=request.queue(id="override"), myplaylist)

# Make nice

myplaylist = crossfade(fade_out=0.01, fade_in=0.01, conservative=true,  myplaylist)

radio = fallback(track_sensitive = false, [myplaylist, security])

# Here, we use FFmpeg to process the audio, and convert it ready for transmission.
# It does not exit cleanly, for reasons I don't understand yet.
#
# We could use output.external, but metadata (e.g. what's playing) doesn't get transferred that way.
# The FFmpeg line is like a broadcast audio chain: we normalize the loudness over a few seconds
# then multi-band compress it, then add a single-band limiter before EBU R.128 normalization with a
# target of -14LUFS.
# The AAC stream is at about 38 kbit/s (variable), so should work almost everywhere.

output.icecast(description="Experimental stream using Liquidsoap", genre="[YOUR GENRE]", name="[YOUR NAME]", host="[YOUR HOST]", port=8000, mount="audio.aac", public=true, url="[FULL URL OF STREAM]", format="audio/aac", password="[YOUR_PASSWORD]", %external(samplerate=32000, channels=2, process="ffmpeg -err_detect ignore_err -report -f s16le -ar 32000 -ac 2 -i pipe:0 -acodec libfdk_aac -vbr 1 -profile:a aac_he_v2 -vn -af dynaudnorm=g=31:m=70:r=1.0,asetnsamples=2048,volume=-18dB,mcompand='0.005\,0.1 6 -47/-40\,-34/-34\,-17/-33 100 | 0.003\,0.05 6 -47/-40\,-34/-34\,-17/-33 400 | 0.000625\,0.0125 6 -47/-40\,-34/-34\,-15/-33 1600 | 0.0001\,0.025 6 -47/-40\,-34/-34\,-31/-31\,-0/-30 6400 | 0\,0.025 6 -38/-31\,-28/-28\,-0/-25 15999',volume=+20dB,alimiter=-4dB,loudnorm=I=-14:LRA=6.0:TP=-0.25:linear=0,aresample=32000 -f adts pipe:1"), radio)



