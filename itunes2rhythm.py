#!/usr/bin/python3
###############################################################################
# itunes2rhythm.py 1.0                                                        #
# Script to convert iTunes xml database to rhythmbox xml database.            #
#                                                                             #
# Original: Jacques Fortier (2004) <jfortier-rb@blergl.net>                   #
# Addons: Yan Zhang (2009) <yanzhangATpostDOTharvardDOTedu>                   #
# Modernisation and fixes : François GUILLIER (2013) <dev @ guillier . org>   #
#                                                                             #
# Note: Will overwrite any existing rhythmbox database - use with care!       #
###############################################################################

# You may also want to modify some of the defaults found below. These are used
# when the given tag is missing from the iTunes db.
DEFAULT_TITLE = "Unknown"
DEFAULT_GENRE = "Unknown"
DEFAULT_ALBUM = "Unknown"
DEFAULT_ARTIST = "Unknown"
DEFAULT_DATE = 0
DEFAULT_MTIME = 0

import sys
import re
import os
import unicodedata
import xml.dom
from xml.dom.minidom import parse
from xml.sax.saxutils import escape
from time import mktime, strptime, timezone
from datetime import datetime, timedelta
from urllib.parse import unquote_to_bytes, quote


def convlocation(location):
    match = re.match(r"file://(\w+/[A-Z]:)(/.+)", location)
    # print("location: "+location)
    if not match:
        # sys.exit("Invalid location: " + location)
        print("Invalid location: " + location)
        return None
    drive = match.group(1)
    path = match.group(2)
    if drive not in cfg["driveMapping"]:
        sys.exit("Unknown drive: %s" % drive)
    mapped_drive = cfg["driveMapping"][drive]
    if mapped_drive is None:
        return None
    # Conversion UTF-8 NFD (Mac) --> UTF-8 NFC (Linux/Windows/W3C/...)
    path = quote(unicodedata.normalize('NFC',
        unquote_to_bytes(path).decode("utf-8")),"/!'(),&~+$")
    if path[-1] == '/':
        path = path[0:-1]
    return "file://" + mapped_drive + path


def convString(string):
    r = []
    for i, ch in enumerate(string):
        r.append(ch if ord(ch) < 128 else "&#x"+"%X" % ord(ch)+";")
    return ''.join(r).strip()


def getStringTag(keytag):
    sibling = getNextSibling(keytag)
    if not sibling:
        return None
    if sibling.tagName != 'string':
        return None
    return sibling.firstChild.data


def getIntegerTag(keytag):
    sibling = getNextSibling(keytag)
    if not sibling:
        return None
    if sibling.tagName != 'integer':
        return None
    return int(sibling.firstChild.data)


def getDateTag(keytag):
    sibling = getNextSibling(keytag)
    if not sibling:
        return None
    if sibling.tagName != 'date':
        return None
    return mktime(strptime(sibling.firstChild.data, '%Y-%m-%dT%H:%M:%SZ')
                 ) - timezone


def getNextSibling(item):
    """ Gets the next sibling that's actually an element. """
    sibling = item.nextSibling
    while sibling:
        if sibling.nodeType == xml.dom.Node.ELEMENT_NODE:
            break
        sibling = sibling.nextSibling
    return sibling

##############
# workhorses #
##############


def writeLibrary(rlib, tracksDict):
    """ Writes library to rlib. Returns a track/location dictionary that we'll
        need later for playlists. """
    trackCount = 0
    timestamp = (datetime.utcnow() - datetime(1970, 1, 1)) \
            // timedelta(seconds=1)
    ourdb = {}  # our tracks db, with matching locations. used for playlists
    rlib.write('<?xml version="1.0" standalone="yes"?>\n')
    rlib.write('<rhythmdb version="1.8">\n')
    for child in tracksDict.childNodes:
        if (child.nodeType != xml.dom.Node.ELEMENT_NODE or
                child.tagName != 'dict'):
            #there are interspersing keys and dicts here. Skip the keys
            continue
        trackCount += 1
        title = DEFAULT_TITLE
        artist = DEFAULT_ARTIST
        album = DEFAULT_ALBUM
        albumArtist = None
        genre = DEFAULT_GENRE
        location = None
        trackNumber = None
        discNumber = None
        fileSize = None
        duration = None
        rating = None
        lastPlayed = None
        playCount = None
        bitrate = None
        date = DEFAULT_DATE
        mtime = DEFAULT_MTIME
        mediaType = ""
        trackType = None
        for keytag in child.childNodes:
            if (keytag.nodeType != xml.dom.Node.ELEMENT_NODE or
                    keytag.tagName != 'key'):
                continue
            if keytag.firstChild.nodeType != xml.dom.Node.TEXT_NODE:
                continue
            keytype = keytag.firstChild.data
            if keytype == 'Name':
                title = getStringTag(keytag)
            elif keytype == 'Artist':
                artist = getStringTag(keytag)
            elif keytype == 'Album Artist':
                albumArtist = getStringTag(keytag)
            elif keytype == 'Album':
                album = getStringTag(keytag)
            elif keytype == 'Genre':
                genre = getStringTag(keytag)
            elif keytype == 'Location':
                location = convlocation(getStringTag(keytag))
            elif keytype == 'Track Number':
                trackNumber = getIntegerTag(keytag)
            elif keytype == 'Disc Number':
                discNumber = getIntegerTag(keytag)
            elif keytype == 'Size':
                fileSize = getIntegerTag(keytag)
            elif keytype == 'Total Time':
                duration = getIntegerTag(keytag) // 1000
            elif keytype == 'Rating':
                rating = getIntegerTag(keytag) // 20
            elif keytype == 'Year':
                year = getIntegerTag(keytag)
                date = year * 365 + ((year - 1517) // 4)
            elif keytype == 'Bit Rate':
                bitrate = getIntegerTag(keytag)
            elif keytype == 'Date Modified':
                mtime = getDateTag(keytag)
            elif keytype == 'Play Date UTC':
                lastPlayed = getDateTag(keytag)
            elif keytype == 'Play Count':
                playCount = getIntegerTag(keytag)
            elif keytype == 'Track ID':
                trackid = getIntegerTag(keytag)
            elif keytype == 'Kind':
                kind = getStringTag(keytag)
                if kind in cfg["mediaTypeMapping"]:
                    mediaType = cfg["mediaTypeMapping"][kind]
            elif keytype == 'Track Type':
                trackType = getStringTag(keytag)
        if (trackType != "File" or trackType == "URL"):
            print("'%s' (ID %d) is remote" % (title, trackid))
            continue
        if not mediaType:
            print("'%s' (ID %d) is not music" % (title, trackid))
            continue
        if not location or not fileSize or not duration:
            print("'%s' (ID %d) has errors" % (title, trackid))
            continue
        ourdb[trackid] = location
        rlib.write('  <entry type="song">\n')
        rlib.write('    <title>%s</title>\n' % convString(escape(title)))
        rlib.write('    <genre>%s</genre>\n' % convString(escape(genre)))
        rlib.write('    <artist>%s</artist>\n' % convString(escape(artist)))
        rlib.write('    <album>%s</album>\n' % convString(escape(album)))
        if trackNumber:
            rlib.write('    <track-number>%d</track-number>\n' % trackNumber)
        if discNumber:
            rlib.write('    <disc-number>%d</disc-number>\n' % discNumber)
        rlib.write('    <duration>%d</duration>\n' % duration)
        rlib.write('    <file-size>%d</file-size>\n' % fileSize)
        rlib.write('    <location>%s</location>\n' % escape(location))
        rlib.write('    <mtime>%d</mtime>\n' % mtime)
        rlib.write('    <last-seen>%d</last-seen>\n' % timestamp)
        if rating:
            rlib.write('    <rating>%d</rating>\n' % rating)
        if lastPlayed and playCount:
            rlib.write('    <play-count>%d</play-count>\n' % playCount)
            rlib.write('    <last-played>%d</last-played>\n' % lastPlayed)
        if bitrate:
            rlib.write('    <bitrate>%d</bitrate>\n' % bitrate)
        rlib.write('    <date>%d</date>\n' % date)
        if mediaType != "":
            rlib.write('    <media-type>%s</media-type>\n' % mediaType)
        if albumArtist:
            rlib.write('    <album-artist>%s</album-artist>\n' %
                    convString(escape(albumArtist)))
        rlib.write('  </entry>\n')

    rlib.write('</rhythmdb>\n')
    rlib.close()
    print("====> %d out of %d songs collected." % (len(ourdb), trackCount))
    return ourdb


def writePlaylists(rplists, defaultlists, plistArray, ourdb):
    """ Writes playlists from plistArray to rplists. Reads a list of playlists
    from defaultlists, which are copied as-is. ourdb is the track/location
    dictionary needed for rhythmbox to find the files. """
    rplists.write('<?xml version="1.0"?>\n')
    rplists.write('<rhythmdb-playlists>\n')

    for line in defaultlists:
        rplists.write(line)

    for child in plistArray.childNodes:
        if child.nodeType != xml.dom.Node.ELEMENT_NODE or \
                child.tagName != 'dict':
            continue
        entries = []
        for keytag in child.childNodes:
            if keytag.nodeType != xml.dom.Node.ELEMENT_NODE or \
                    keytag.tagName != 'key':
                continue
            if keytag.firstChild.nodeType != xml.dom.Node.TEXT_NODE:
                continue
            keytype = keytag.firstChild.data
            if keytype == 'Name':
                title = getStringTag(keytag)
            elif keytype == 'Playlist Items':
                idArray = getNextSibling(keytag)
                assert idArray.tagName == 'array', \
                        "array must follow 'Playlist Items'"
                for song in idArray.childNodes:
                    if song.nodeType != xml.dom.Node.ELEMENT_NODE or \
                            song.tagName != 'dict':
                        continue
                    songKey = getNextSibling(song.firstChild)
                    assert songKey.tagName == 'key'
                    location = ourdb.get(getIntegerTag(songKey))
                    if location:
                        entries.append(location)
        assert title, "error: titleless playlist"
        if title in cfg["ignoreList"]:
            continue
        if not entries:
            continue
        rplists.write('  <playlist name="%s" type="static">\n' % escape(title))
        for location in entries:
            rplists.write('    <location>%s</location>\n' % escape(location))
        rplists.write('  </playlist>\n')
        print("'%s' %d" % (escape(title), len(entries)))
    rplists.write('</rhythmdb-playlists>\n')
    rplists.close()

#################
# actual script #
#################

cfg = {}
exec(open(sys.argv[0][:-2]+"conf").read(), cfg)

itunesdb = parse(cfg["iLib"])
plist = itunesdb.documentElement
assert plist.tagName == 'plist', 'Not a valid itunes db: No plist tag'
tracksDict = None
plistArray = None
bigDict = getNextSibling(plist.firstChild)
assert bigDict.tagName == 'dict', 'plist must contain a dict'
for bigDictItem in bigDict.childNodes:
    if (bigDictItem.nodeType == xml.dom.Node.ELEMENT_NODE and
            bigDictItem.tagName == 'key'):
        if (bigDictItem.firstChild.data == 'Tracks'):
            tracksDict = getNextSibling(bigDictItem)
            assert tracksDict.tagName == 'dict', "need <dict> after 'Tracks'"
        if (bigDictItem.firstChild.data == 'Playlists'):
            plistArray = getNextSibling(bigDictItem)
            assert plistArray.tagName == 'array', \
                    "need <array> after 'Playlists'"
assert tracksDict, 'Could not find tracks dict'

dlists = open(os.path.join(os.path.dirname(sys.argv[0]),
                           "defaultplaylists"),
                           'r')
rlib = open(cfg["rLib"], 'w')
rlists = open(cfg["rLists"], 'w')
ourdb = writeLibrary(rlib, tracksDict)
writePlaylists(rlists, dlists, plistArray, ourdb)
