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
// Changes background colour of selected item
// and also those of all other identical items
// because each item has a DOM id corresponding to
// the hash of the audio file it refers to.

var filesToRemove = [];

// Use this to remove an element by value from an array

function arrayRemove(arr, value) {
    return arr.filter(function(ele) {
        return ele != value;
        });
}

// Makes sure only one audio element is playing at the same time
function onlyPlayOneIn(container) {
    container.addEventListener("play", function(event) {
    audio_elements = container.getElementsByTagName("audio")
        for(i=0; i < audio_elements.length; i++) {
            audio_element = audio_elements[i];
            if (audio_element !== event.target) {
                audio_element.pause();
            }
        }
    }, true);
}

document.addEventListener("DOMContentLoaded", function() {
    onlyPlayOneIn(document.body);
});
    
const removeDuplicates = (duplicates) => {
    const unique = Array.from(new Set(duplicates));
    return unique;
}


document.querySelector('#dupes').addEventListener('click', (ev) => {
        const cellid = ev.target.className;
    if (cellid === undefined) {
//        console.log("undefined cell");
        return;
    }
//    console.log(cellid);
    var all = document.getElementsByClassName(cellid);
    for (var i = 0; i < all.length; i++) {
//        console.log(getComputedStyle(all[i]).getPropertyValue("background-color"));
        if (getComputedStyle(all[i]).getPropertyValue('background-color') !== 'rgb(255, 160, 160)') {
            all[i].style.backgroundColor = '#FFA0A0';
            // Add the filename contained in the cell (it's the second <td> element)
            // to the list of filenames to be deleted
            // Obscure construction to get around selector starting with number
            var fileToCut = document.querySelector("[class='" + cellid + "']").textContent.split("\\n", 1)[0];
            filesToRemove.push(fileToCut);
            console.log("Before dedup.");
            console.log(filesToRemove);
            // Make this an array with unique values
            filesToRemove = removeDuplicates(filesToRemove);
            document.getElementById("todelete").innerHTML = filesToRemove.join("\\n");
            console.log("After dedup.");
            console.log(filesToRemove);
        } 
        else {
            all[i].style.backgroundColor = 'white';
            // This must be removed from the filesToRemove array.
            // We assume that this array has only one item corresponding to the value
            // we are removing.
            var fileToCut = document.querySelector("[class='" + cellid + "']").textContent.split("\\n", 1)[0];
            filesToRemove = arrayRemove(filesToRemove, fileToCut);
            document.getElementById("todelete").innerHTML = filesToRemove.toString();
            console.log(filesToRemove);            
       }
    }    
});

// Code to download the text contained within a text area
const downloadToFile = (content, filename, contentType) => {
    const a = document.createElement('a');
    const file = new Blob([content], {type: contentType});
    a.href = URL.createObjectURL(file);
    a.download = filename;
    a.click();
    
      URL.revokeObjectURL(a.href);
};

// Creates the action to download the text area, above
document.querySelector('#savedelete').addEventListener('click', () => {
    const textArea = document.querySelector('#todelete');
    downloadToFile(textArea.value, 'delete-these-files.txt', 'text/plain');
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
        f"{float(match):.2f}</td>\n"
        f"<td class=\"{item1['hash']}\">{item1['filename']}<br />\n"
        f"{item1['artist']}<br />{item1['title']}<br />\n"
        f"{int(item1['bitrate']) / 1000:,.0f}kbit/s, {datetime.timedelta(seconds=round(float(item1['duration']),0))}, "
        f"{int(item1['size']) / 1000:,.0f}k, {int(item1['samplerate']):,}Hz<br />\n"
        f"{item1['codec']}<br />\n"
        f"<audio controls style=\"width: 100%;\"><source src=\"{ROOT}/{item1['filename']}\"></audio>"
        f"</td>\n"
        f"<td class=\"{item2['hash']}\">{item2['filename']}<br />\n"
        f"{item2['artist']}<br />{item2['title']}<br />\n"
        f"{int(item2['bitrate']) / 1000:,.0f}kbit/s, {datetime.timedelta(seconds=round(float(item2['duration']),0))}, "
        f"{int(item2['size']) / 1000:,.0f}k, {int(item2['samplerate']):,}Hz<br />\n"
        f"{item2['codec']}<br />\n"
        f"<audio controls style=\"width: 100%;\"><source src=\"{ROOT}/{item2['filename']}\"></audio>"
        f"</td></tr>\n"
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
    op.write('<a href="" id="dl" style="font-size: large;"></a>')
    op.write('<textarea cols="160" rows="24" wrap="soft" placeholder="List of files to delete" id="todelete"></textarea>')
    op.write('<button id="savedelete">SAVE</button>')
    op.write(JAVASCRIPT)

    op.write('</body></html>')

print(f'Table is now in {OUTPUT}')
