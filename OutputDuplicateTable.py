# Output HTML form corresponding to files requiring consideration
import json
import subprocess
import csv
import os.path
import argparse
import datetime

# ROOT = "Z:/radio/mez3/"

FFPROBE = 'ffprobe.exe'
CREATE_NO_WINDOW = 0x08000000


STYLE = """
<style>
body {font-family: sans-serif,arial,helvetica;
font-size: 10px;
font-stretch: semi-condensed;}
table, th, td {
border: 2px solid black;
border-collapse: collapse;
}
</style>
"""

JAVASCRIPT = """
<script>
document.querySelector('#dupes').addEventListener('click', (ev) => {
        const cellid = ev.target.className;
    if (cellid === undefined) {
        console.log("undefined cell");
        return;
    }
    console.log(cellid);
    var all = document.getElementsByClassName(cellid);
    for (var i = 0; i < all.length; i++) {
        console.log(getComputedStyle(all[i]).getPropertyValue("background-color"));
        if (getComputedStyle(all[i]).getPropertyValue('background-color') !== 'rgb(85, 255, 255)') {
            all[i].style.backgroundColor = '#FFA0A0';
        } 
        else {
            all[i].style.backgroundColor = 'white';
       }
    }    
});
</script>   


"""


def findhash(inputfilename):
    # Takes a filename, returns the hash contained within it
    fullfilename = os.path.join(ROOT, inputfilename)
    return fullfilename.split('.')[-2]


def returnmetadata(inputfilename):
    # Returns a dictionary of interesting metadata within a file
    completedprocess = None
    fullfilename = os.path.join(ROOT, inputfilename)
    print(fullfilename)
    myargs = [FFPROBE, '-v', 'quiet', '-print_format', 'json', '-show_entries', 'format : stream', fullfilename]
    try:
        completedprocess = subprocess.run(myargs, capture_output=True, encoding='utf-8',
                                          check=True, creationflags=CREATE_NO_WINDOW)
    except subprocess.CalledProcessError:
        print(f"ERROR: Querying the file {fullfilename} produced an error. Does the file exist?")
        exit(1)
    # This sets all dictionary keys to lower case because the metadata keys are often mixed
    data = json.loads(completedprocess.stdout)
    # print(fullfilename)
    # print(data)
    tags = data['format']['tags']
    lowercasetags = dict((k.lower(), v) for k, v in tags.items())

    return {'duration': data['format']['duration'],
            'size': data['format']['size'],
            'bitrate': data['format']['bit_rate'],
            'codec': data['streams'][0]['codec_long_name'],
            'rate': data['streams'][0]['sample_rate'],
            'title': lowercasetags.get('title'),
            'artist': lowercasetags.get('artist'), }


def convertfirsttofloat(values):
    return [float(values[0]), values[1], values[2]]


def populatecsv(csvfilename):
    # Must specify unicode, for filenames using extended characters
    with open(csvfilename, 'r', newline='', encoding='utf-8') as handle:
        incomingtable = list(csv.reader(handle))
        return incomingtable


def addmetadata(inputtable):
    outgoing = list()
    # To each row, add bitrate, duration, size, title, artist, codec, rate and hash
    for row in inputtable:
        temprow = list()
        # Match factor
        temprow.append(row[0])
        # first track name
        temprow.append(row[1])
        meta = returnmetadata(row[1])
        temprow.extend((meta['bitrate'], meta['duration'], meta['size'], meta['title'], meta['artist'], meta['codec'],
                        meta['rate']))
        temprow.append(findhash(row[1]))
        # second track name
        temprow.append(row[2])
        meta = returnmetadata(row[2])
        temprow.extend((meta['bitrate'], meta['duration'], meta['size'], meta['title'], meta['artist'], meta['codec'],
                        meta['rate']))
        temprow.append(findhash(row[2]))
        outgoing.append(temprow)
    return outgoing


def createcelldata(row):
    # Data in row is:
    # match, filename1, bitrate1, duration1, size1, title1, artist1, codec1, samplerate1, hash1,
    # filename2, bitrate2, duration2, size2, title2, artist2, codec2, samplerate2, hash2
    match = row[0]

    item1 = {'filename': row[1],
             'bitrate': row[2],
             'duration': row[3],
             'size': row[4],
             'title': row[5],
             'artist': row[6],
             'codec': row[7],
             'samplerate': row[8],
             'hash': row[9]
             }

    item2 = {'filename': row[10],
             'bitrate': row[11],
             'duration': row[12],
             'size': row[13],
             'title': row[14],
             'artist': row[15],
             'codec': row[16],
             'samplerate': row[17],
             'hash': row[18]
             }

    html = (
        f"<tr><td>"
        f"{float(match):.2f}</td>"
        f"<td class=\"{item1['hash']}\">{item1['filename']}<br />"
        f"{item1['artist']}<br />{item1['title']}<br />"
        f"{int(item1['bitrate']) / 1000:,.0f}kbit/s, {datetime.timedelta(seconds=round(float(item1['duration']),0))}, "
        f"{int(item1['size']) / 1000:,.0f}k, {int(item1['samplerate']):,}Hz<br />"
        f"{item1['codec']}"
        f"</td>"
        f"<td class=\"{item2['hash']}\">{item2['filename']}<br />"
        f"{item2['artist']}<br />{item2['title']}<br />"
        f"{int(item2['bitrate']) / 1000:,.0f}kbit/s, {datetime.timedelta(seconds=round(float(item2['duration']),0))}, "
        f"{int(item2['size']) / 1000:,.0f}k, {int(item2['samplerate']):,}Hz<br />"
        f"{item2['codec']}"
        f"</td></tr>"
    )

    return html


# START HERE

parser = argparse.ArgumentParser(description='Creates helpful web-page from list of duplicate audio files')
parser.add_argument('-o', '--output', default='duplicates_table.html',
                    help='Specify output file. Will be overwritten. Default: %(default)s')
parser.add_argument('-r', '--root', default='', help='Add a root to files in the CSV duplicates list.')
parser.add_argument('csvfile', default='output.csv', nargs='?',
                    help='Specify CSV duplicates list. Default: %(default)s')

args = parser.parse_args()

OUTPUT = args.output
ROOT = args.root
CSVFILE = args.csvfile

table = list(sorted(populatecsv(CSVFILE), key=lambda x: float(x[0]), reverse=True))
# Now open up the table, adding many fields at the end of each row:
# bitrate, duration, size, title, artist, codec, samplerate, hash for BOTH files
fulltable = addmetadata(table)

with open(OUTPUT, 'w', encoding='utf-8') as op:
    op.write('<html><head>')
    op.write(STYLE)
    op.write('</head><body>')
    op.write('<table id="dupes">')
    for duplicaterow in fulltable:
        op.write(createcelldata(duplicaterow))
    op.write('</table>')
    op.write(JAVASCRIPT)
    op.write('</body></html')

print(f'Table is now in {OUTPUT}')
