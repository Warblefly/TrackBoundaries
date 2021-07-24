This is how to import a playlist.

1. Export a playlist in m3u8 format from the auditioning software you use e.g. Foobar2000
2. Change the root of the files in the playlist thus:\
`convertplaylist.py -i <INPUT_PLAYLIST> -o <OUTPUT_PLAYLIST> -r <Root of your music directory>`
3. Annotate every line in the output file, above, with track starts, track fade-outs, duration and volume, and then wrap each track into a .mka file with metadata added:\
`cue_playlist.py -m <MEZZANINE_DIRECTORY> <PLAYLIST>`
4. This will leave you with a new directory full of music files, and a playlist pointing to them, ending '-processed.m3u8'
5. If combining this new playlist with other playlists:\
`combineplaylists.py -i <PLAYLIST1> -i <PLAYLIST2> ... -o <OUTPUT>`
6. Move into the mezzanine directory containing the newly-wrapped music files
7. Ensure there are no .csv files, or any other non-music files.
8. Create chromaprints of every music file present.\
`chromaprint_db.py "*"`
10. The output file will be called 'chromaprints.csv'
11. Move this to wherever you want to process it. I use another, large multi-processor machine.
12. Execute the de-duplication table generator:\
`dedup.py`
14. On its output, duplicates.csv, execute the HTML/Javascript media player generator, remembering that the PATH_TO_MUSIC_DIRECTORY must be where your web browser can find the music files:\
`OutputDuplicateTable.py -r <PATH_TO_MUSIC_DIRECTORY>`
16. Open the HTML page this produces in a modern browser.
17. Each line shows two similar files, together with a numerical measure of their similarity (in %) and a player for each. There is also a collection of metadata including title, artist, duration, codec, sampling rate and bitrate.
18. Click on the file you **don't** want to keep. Consider sample rate, bitrate and other factors. This turns the entry, and all identical entries, red.
19. Having traversed the entire table, look for the list of files at the bottom. Click SAVE to save this list as a text file.
20. From the directory containing all music files, run the weeding program:\
`weedplaylist.py <ORIGINAL_PLAYLIST> <TEXT_LIST_OF_FILES_TO_REMOVE>`
18. Two files are output: one ends '\_weedsonly.m3u8', being files removed from the original playlist; another ends '\_weeded.m3u8', being the playlist of files remaining. There is also a new directory within the music files directory, that the weeded music files are moved into.
19. Replace your on-air playlist with the file ending '\_weeded.m3u8'.
20. Keep the weeded files carefully.
