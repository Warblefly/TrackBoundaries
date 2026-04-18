#!/usr/bin/liquidsoap

# This is the live script (redacted) in use in April 2026
# Liquidsoap 2.4.3 latest

# To help with learning the internals
settings.server.log.level.set(4)
settings.log.level.set(4)
settings.log.file.set(true)

# Put location of required Liquidsoap log file here
settings.log.file.path.set("/home/liquidsoap/musictoo.log")

# Keep FFmpeg debugging information too, so we know what's happening
settings.ffmpeg.log.capture.set(true)
settings.ffmpeg.log.verbosity.set("info")

# Need this to insert news when it is due
settings.server.telnet.set(true)
settings.server.telnet.bind_addr.set("0.0.0.0")
settings.server.telnet.port.set(1235)
settings.server.timeout.set(90.0)

# How long to wait if we try to access something?
settings.request.timeout.set(60.0)

# Save some memory
settings.init.compact_before_start.set(true)

# Calculate durations on the fly. Takes up CPU time though
settings.request.metadata_decoders.duration.set(true)

# Let autocue data be generated, for our human-style crossfading/overlapping
enable_autocue_metadata()

# Make sure we USE the generated autocue data
settings.autocue.preferred.set("internal")
settings.autocue.internal.metadata_override.set([""])

# Process quite slowly with loudness calculation, so we don't claim too much CPU
settings.lufs.decoding_ratio.set(25.0)

# A decent level, avoiding the risk of clipping
settings.autocue.internal.lufs_target.set(-23.0)

# Use our own autocue detected loudness, not ReplayGain in metadata
settings.autocue.amplify_behavior.set("override")

# Long-ish maximum crossfade
settings.autocue.internal.max_overlap.set(15.0)

# Don't process autocue data too quickly: keep CPU usage down
settings.autocue.internal.ratio.set(25.0)
settings.autocue.internal.timeout.set(100.0)

# Use only FFmpeg for decoding, and restrict file suffixes to that which we use
settings.decoder.decoders.set(["ffmpeg"])
settings.decoder.file_extensions.ffmpeg.set(["mka"])
settings.decoder.file_extensions.id3.set(["mka"])
settings.decoder.file_extensions.ogg_metadata.set(["mka"])
settings.decoder.file_extensions.flac_metadata.set(["mka"])
settings.decoder.file_extensions.video_metadata.set(["mka"])
settings.decoder.file_extensions.image_metadata.set(["mka"])
settings.decoder.mime_types.ffmpeg.set(["audio/x-matroska"])
settings.decoder.mime_types.id3.set(["audio/x-matroska"])
settings.decoder.mime_types.flac_metadata.set(["audio/x-matroska"])
settings.decoder.mime_types.ogg_metadata.set(["audio/x-matroska"])
settings.decoder.mime_types.video_metadata.set(["audio/x-matroska"])
settings.decoder.mime_types.image_metadata.set(["audio/x-matroska"])

# Garbage collect fairly often
runtime.gc.set(runtime.gc.get().{space_overhead=20, allocation_policy=2})

# Simplified log, for music reporting
airlog_file = "/home/liquidsoap/air_log.jsonl"

# audio processing for high quality stream
def audio_process(s) =
  def mkfilter(graph) =
    let { audio = audio_track } = source.tracks(s)
    audio_track = ffmpeg.filter.audio.input(graph, audio_track)
# Our internal -23LUFS, the standard EBU level, is good for avoiding distortion, but Internet streams are generally a bit louder
    audio_track = ffmpeg.filter.loudnorm(graph, audio_track, i=-17.0, lra=5.0, tp=-0.25, linear=false)
    audio_track = ffmpeg.filter.aresample(graph, audio_track, sample_rate=44100)
    audio_track = ffmpeg.filter.audio.output(graph, audio_track)

    source({
        audio = audio_track,
        metadata = track.metadata(audio_track),
        track_marks = track.track_marks(audio_track)
        })
  end

  ffmpeg.filter.create(mkfilter)
end

def audio_process_wrap(s) =
  s = ffmpeg.raw.encode.audio(%ffmpeg(%audio.raw), s)
  s = audio_process(s)
# We can return this raw because the encoder is %ffmpeg, and it will take raw
  s
end


# Audio processing for the compressed stream

def audio_process_multi(s) =
  def mkfilter_multi(graph) =
    let { audio = audio_track } = source.tracks(s)
    audio_track = ffmpeg.filter.audio.input(graph, audio_track)
# Lower the sampling rate: saves Internet bandwidth
    audio_track = ffmpeg.filter.aresample(graph, audio_track, sample_rate=24000)
    audio_track = ffmpeg.filter.dynaudnorm(graph, audio_track, gausssize=7, correctdc=true, altboundary=true, maxgain=80., b=true, targetrms=1.)
    audio_track = ffmpeg.filter.volume(graph, audio_track, volume="-18dB", precision=2, replaygain=0)
# Optimod-style multi-band compression, but much less sophisticated
    audio_track = ffmpeg.filter.mcompand(graph, audio_track, args="0.005,0.1 6 -47/-37,-34/-34,-17/-33 90 | 0.003,0.05 6 -47/-40,-34/-34,-17/-33 180 | 0.003,0.05 6 -47/-40,-34/-34,-17/-33 360 | 0.000625,0.03 6 -47/-40,-34/-34,-17/-33 1600 | 0.000625,0.03 6 -47/-40,-34/-34,-17/-33 2800 | 0.0001,0.025 6 -47/-35,-34/-34,-17/-33 4800 | 0,0.025 6 -47/-35,-34/-34,-17/-33 8192 | 0,0.025 6 -47/-40,-34/-34,-17/-33 11999")
    audio_track = ffmpeg.filter.volume(graph, audio_track, volume="+20dB", precision=2, replaygain=0)
# To prevent excess true peaks, one ought to resample up and down, but this is CPU heavy, and we are not modulating a transmitter
#    audio = ffmpeg.filter.aresample(graph, audio, sample_rate=192000)
    audio_track = ffmpeg.filter.alimiter(graph, audio_track, limit=0.7, attack=3., release=50., asc=true, asc_level=1., level=true)
#    audio = ffmpeg.filter.aresample(graph, audio, sample_rate=24000)
    audio_track = ffmpeg.filter.audio.output(graph, audio_track)

    source({
        audio = audio_track,
        metadata = track.metadata(audio_track),
        track_marks = track.track_marks(audio_track)
        })
  end

  ffmpeg.filter.create(mkfilter_multi)
end

def audio_process_multi_wrap(s) =
  s = ffmpeg.raw.encode.audio(%ffmpeg(%audio.raw), s)
  s = audio_process_multi(s)
# Just return the FFmpeg raw audio because the encoder will accept this.
  s
end

# Function to insert correct metadata into Icecast server
def handle_metadata(m) =
        log.info("*******************METADATA***********")
        t = m["title"]
        a = m["artist"]
        ta = if t == "" then "Unknown title" else t end
        aa = if a == "" then "Unknown artist" else a end
        log.info("Title is \"" ^ ta ^ "\"")
  log.info("Artist is \"" ^ aa ^ "\"")
  icy.update_metadata(host="127.0.0.1", port=8000, password="[REDACTED]", mount="audio.aac", [("title", ta), ("artist", aa)])
  icy.update_metadata(host="127.0.0.1", port=8000, password="[REDACTED]", mount="audio-hifi.aac", [("title", ta), ("artist", aa)])
end


# Simple sanitiser for JSON string values going into our log:
# - Replace double quotes with single quotes
# - Replace newlines, carriage returns, and tabs with spaces
def json_safe(s) =
  s = string.replace(pattern="\"", (fun(_) -> "'"), s)
  s = string.replace(pattern="\n", (fun(_) -> " "), s)
  s = string.replace(pattern="\r", (fun(_) -> " "), s)
  s = string.replace(pattern="\t", (fun(_) -> " "), s)
s
end

def jstr(s) = "\"" ^ json_safe(s) ^ "\"" end

# Music reporting log, for curious observers
def log_air_event(m) =
  # Human-readable time, e.g. "2026-04-01 12:34:56"
  iso_time = time.string("%Y-%m-%d %H:%M:%S")

  # Basic metadata
  title    = m["title"]
  artist   = m["artist"]
  album    = m["album"]
  genre    = m["genre"]
  filepath = m["filename"]  # avoid shadowing the file module

  title  = if title  == "" then "Unknown title"  else title  end
  artist = if artist == "" then "Unknown artist" else artist end

  # Basename from filename
  basename =
    if filepath == "" then
      ""
    else
      let parts = string.split(separator="/", filepath)
      list.nth(default="", parts, list.length(parts) - 1)
    end

  # Autocue / crossfade / amplification metadata
  cue_in          = m["liq_cue_in"]
  cue_out         = m["liq_cue_out"]
  fade_in         = m["liq_fade_in"]
  fade_out        = m["liq_fade_out"]
  cross_start     = m["liq_cross_start_duration"]
  cross_end       = m["liq_cross_end_duration"]
  cross_max_start = m["liq_cross_max_start_duration"]
  amplify_t         = m["liq_amplify"]
  duration_t        = m["duration"]

  # Build one JSON object per line (JSON Lines)
  entry =
    "{"
    ^ "\"iso_time\":"         ^ jstr(iso_time)
    ^ ",\"filename\":"        ^ jstr(basename)
    ^ ",\"title\":"           ^ jstr(title)
    ^ ",\"artist\":"          ^ jstr(artist)
    ^ ",\"album\":"           ^ jstr(album)
    ^ ",\"genre\":"           ^ jstr(genre)
    ^ ",\"duration\":"        ^ jstr(duration_t)
    ^ ",\"cue_in\":"          ^ jstr(cue_in)
    ^ ",\"cue_out\":"         ^ jstr(cue_out)
    ^ ",\"fade_in\":"         ^ jstr(fade_in)
    ^ ",\"fade_out\":"        ^ jstr(fade_out)
    ^ ",\"cross_start\":"     ^ jstr(cross_start)
    ^ ",\"cross_end\":"       ^ jstr(cross_end)
    ^ ",\"cross_max_start\":" ^ jstr(cross_max_start)
    ^ ",\"amplify\":"         ^ jstr(amplify_t)
    ^ "}\n"

  file.write(append=true, data=entry, airlog_file)
end

# Here's the playlist
myplaylist = playlist(reload_mode="watch", mime_type="application/x-mpegURL", "/home/john/src/radio/mez4.m3u8")

# Add the news
myplaylist = fallback(track_sensitive=true, transition_length=30.0, [request.queue(id="override"), myplaylist])

# Do amplification before we lose track boundaries
myplaylist = amplify(1., override="liq_amplify", myplaylist)

# Handle metadata before we lose track boundaries and go into the FFmpeg filters
# There is a delay, so the first track can be given metadata, though it takes time to start
# because of the FFmpeg filters and an associated buffer()
myplaylist.on_metadata(synchronous=true, fun(myplaylist) -> thread.run(delay=10.0,{handle_metadata(myplaylist)}))

# Log track information without additional debugging
myplaylist.on_metadata(synchronous=true, fun(myplaylist) -> thread.run({log_air_event(myplaylist)}))

# Perform the crossfades
myplaylist = crossfade(myplaylist)

# This is the EBU R.128 loudness-adjusted higher quality stream
radio = audio_process_wrap(myplaylist)

# This is the lower-quality highly compressed stream
radio_comp = audio_process_multi_wrap(buffer(buffer=10.0, myplaylist))

# Here's the high bandwidth Icecast stream - AAC with SBR, no parametric stereo, highest VBR quality
output.icecast(
%ffmpeg(
format="adts",
  %audio.raw(codec="libfdk_aac", samplerate=44100, vbr=5, afterburner=1, profile="aac_he")),
  send_icy_metadata=false,
  fallible=true,
  description="Music Too - Freeform music and world news",
  genre="Freeform",
  name="Music Too",
  host="127.0.0.1",
  port=8000,
  mount="audio-hifi.aac",
  method="source",
  public=true,
  url="http://warblefly.sytes.net:8000/audio-hifi.aac",
  timeout=240.0,
  format="audio/aacp",
  password="[REDACTED]",
  radio
 )


# Here's the compressed stream - AAC with SBR and Parametric Stereo, lowest VBR quality
output.icecast(
%ffmpeg(
format="adts",
  %audio.raw(codec="libfdk_aac", samplerate=24000, vbr=1, afterburner=1, profile="aac_he_v2")),
  send_icy_metadata=false,
  fallible=true,
  description="Music Too - Freeform music and world news",
  genre="Freeform",
  name="Music Too",
  host="127.0.0.1",
  port=8000,
  mount="audio.aac",
  method="source",
  public=true,
  url="http://warblefly.sytes.net:8000/audio.aac",
  timeout=240.0,
  format="audio/aacp",
  password="[REDACTED]",
  radio_comp
 )
