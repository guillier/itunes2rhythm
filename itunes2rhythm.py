#!/usr/bin/python
###############################################################################
# itunes2rhythm.py 0.1                                                        #
# Script to convert iTunes xml database to rhythmbox xml database.            #
# Original: Jacques Fortier (2004) <jfortier-rb@blergl.net>                   #
# Addons: Yan Zhang (2009) <yanzhangATpostDOTharvardDOTedu>                   #
#                                                                             #
# Note: Will overwrite any existing rhythmbox database - use with care!       #
###############################################################################

# You may also want to modify some of the defaults found below. These are used
# when the given tag is missing from the iTunes db.
DEFAULT_TITLE = "Unknown"
DEFAULT_GENRE = "Unknown"
DEFAULT_ALBUM = "Unknown"
DEFAULT_ARTIST = "Unknown"
DEFAULT_RATING = 0
DEFAULT_AUTORATE = 1
# seems unnecessary. I just don't write a key when it is missing - YZ
DEFAULT_TRACKNUMBER = -1 
DEFUALT_MTIME = 0
# playlists with these names will be ignored during conversion.
ignoreList = ['Library', 
              'Music', 
              'TV Shows', 
              'Podcasts', 
              'Genius', 
              'iTunes DJ']

from time import mktime, strptime, localtime, timezone
from xml.dom.minidom import parse
from xml.sax.saxutils import escape, unescape
import xml.dom
import sys
import re

def convtime( strtime ):
    return mktime( strptime( strtime, '%Y-%m-%dT%H:%M:%SZ' ) ) - timezone 

def getStringTag( keytag ): 
    sibling = getNextSibling(keytag)
    if not sibling:
        return None
    if sibling.tagName != 'string': 
        return None 
    return sibling.firstChild.data 

def getIntegerTag( keytag ): 
    sibling = getNextSibling(keytag)
    if not sibling:
        return None
    if sibling.tagName != 'integer': 
        return None 
    return int(sibling.firstChild.data) 

def getDateTag( keytag ): 
    sibling = getNextSibling(keytag)
    if not sibling:
        return None
    if sibling.tagName != 'date': 
        return None 
    return convtime(sibling.firstChild.data) 

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
    ourdb = {} # our tracks db, with matching locations. used for playlists
    rlib.write(('<?xml version="1.0" standalone="yes"?>').encode("utf-8") + '\n')
    rlib.write(('<rhythmdb version="1.0">').encode("utf-8") + '\n')
    for child in tracksDict.childNodes:
        if child.nodeType != xml.dom.Node.ELEMENT_NODE or child.tagName != 'dict':
            #there are interspersing keys and dicts here. Skip the keys
            continue
        trackCount += 1
        title = None
        artist = None
        album = None
        genre = None
        location = None
        tracknumber = None
        filesize = None
        duration = None
        rating = None
        autorate = None
        lastplayed = None
        playcount = None
        mtime = None
        for keytag in child.childNodes:
            if keytag.nodeType != xml.dom.Node.ELEMENT_NODE or keytag.tagName != 'key':
                continue
            if keytag.firstChild.nodeType != xml.dom.Node.TEXT_NODE:
                continue
            keytype = keytag.firstChild.data
            if keytype == 'Name': 
                title = getStringTag( keytag ) 
            elif keytype == 'Artist': 
                artist = getStringTag( keytag ) 
            elif keytype == 'Album': 
                album = getStringTag( keytag ) 
            elif keytype == 'Genre': 
                genre = getStringTag( keytag ) 
            elif keytype == 'Location': 
    #            location = convlocation( getStringTag( keytag ) ) 
                location = getStringTag( keytag ) 
            elif keytype == 'Track Number': 
                tracknumber = getIntegerTag( keytag ) 
            elif keytype == 'Size': 
                filesize = getIntegerTag( keytag ) 
            elif keytype == 'Total Time': 
                duration = getIntegerTag( keytag ) / 1000 
            elif keytype == 'Rating': 
                rating = getIntegerTag( keytag ) / 20.0
            elif keytype == 'Date Modified': 
                mtime = getDateTag( keytag ) 
            elif keytype == 'Play Date UTC': 
                lastplayed = getDateTag( keytag ) 
            elif keytype == 'Play Count': 
                playcount = getIntegerTag( keytag ) 
            elif keytype == 'Track ID':
                trackid = getIntegerTag (keytag)
        if not location or not filesize or not duration:
            print "'%s' (ID %d) has errors" % (title, trackid)
            continue
        if not title:
            title = DEFAULT_TITLE
        if not artist:
            artist = DEFAULT_ARTIST
        if not album:
            album = DEFAULT_ALBUM
        if not genre:
            genre = DEFAULT_GENRE
        if not rating:
            rating = DEFAULT_RATING
        if not autorate:
            autorate = DEFAULT_AUTORATE
        if not mtime:
            mtime = DEFAULT_MTIME
        ourdb[trackid] = location
        rlib.write(('  <entry type="song">\n').encode('utf-8'))
        rlib.write(('    <title>%s</title>\n' % escape(title)).encode('utf-8'))
        rlib.write(('    <genre>%s</genre>\n' % escape(genre)).encode('utf-8'))
        rlib.write(('    <artist>%s</artist>\n' % escape(artist)).encode('utf-8'))
        rlib.write(('    <album>%s</album>\n' % escape(album)).encode('utf-8'))
        if tracknumber:
            rlib.write(('    <track-number>%d</track-number>\n' % tracknumber).encode('utf-8'))
        rlib.write(('    <duration>%d</duration>\n' % duration).encode('utf-8'))
        rlib.write(('    <file-size>%d</file-size>\n' % filesize).encode('utf-8'))
        rlib.write(('    <location>%s</location>\n' % escape(location)).encode('utf-8'))
        rlib.write(('    <mtime>%d</mtime>\n' % mtime).encode('utf-8'))
        rlib.write(('    <rating>%0.6f</rating>\n' % rating).encode('utf-8'))
        rlib.write(('    <auto-rate>%d</auto-rate>\n' % autorate).encode('utf-8'))
        if lastplayed and playcount:
            rlib.write(('    <play-count>%d</play-count>\n' % playcount).encode('utf-8'))
            rlib.write(('    <last-played>%d</last-played>\n' % lastplayed).encode('utf-8'))
        rlib.write(('    <mimetype></mimetype>\n').encode('utf-8'))
        rlib.write(('  </entry>\n').encode('utf-8'))

    rlib.write(('</rhythmdb>').encode('utf-8') + '\n')
    rlib.close()
    print "%d out of %d songs collected." % (len(ourdb), trackCount)
    return ourdb

def writePlaylists(rplists, defaultlists, plistArray, ourdb):
    """ Writes playlists from plistArray to rplists. Reads a list of playlists from
        defaultlists, which are copied as-is. ourdb is the track/location dictionary
        needed for rhythmbox to find the files. """
    rplists.write(('<?xml version="1.0"?>\n').encode("utf-8"))
    rplists.write(('<rhythmdb-playlists>\n').encode("utf-8"))

    for line in defaultlists:
        rplists.write(line)

    for child in plistArray.childNodes:
        if child.nodeType != xml.dom.Node.ELEMENT_NODE or child.tagName != 'dict':
            continue
        listName = None
        trackIDs = []
        for keytag in child.childNodes:
            if keytag.nodeType != xml.dom.Node.ELEMENT_NODE or keytag.tagName != 'key':
                continue
            if keytag.firstChild.nodeType != xml.dom.Node.TEXT_NODE:
                continue
            keytype = keytag.firstChild.data
            if keytype == 'Name':
                title = getStringTag( keytag )
            elif keytype == 'Playlist Items':
                idArray = getNextSibling(keytag)
                assert idArray.tagName == 'array', "array must follow 'Playlist Items'"
                for song in idArray.childNodes:
                    if song.nodeType != xml.dom.Node.ELEMENT_NODE or song.tagName != 'dict':
                        continue
                    songKey = getNextSibling(song.firstChild)
                    assert songKey.tagName == 'key'
                    trackIDs.append(getIntegerTag(songKey))
        assert title, "error: titleless playlist"
        if title in ignoreList:
            continue
        rplists.write(('  <playlist name="%s" type = "static">\n' % escape(title)).encode('utf-8'))
        for track in trackIDs:
            location = ourdb.get(track)
            if location:
                rplists.write(('    <location>%s</location>\n' % escape(location)).encode('utf-8'))
        rplists.write(('  </playlist>\n').encode('utf-8'))
        print '%s %d' % (escape(title), len(trackIDs))
    rplists.write(('</rhythmdb-playlists>\n').encode("utf-8"))
    rplists.close()

#################
# actual script #
#################

itunesdb = parse(sys.argv[1])
plist = itunesdb.documentElement
assert plist.tagName == 'plist', 'Not a valid itunes db: No plist tag'
tracksDict = None
plistArray = None
bigDict = getNextSibling(plist.firstChild)
assert bigDict.tagName == 'dict', 'plist must contain a dict'
for bigDictItem in bigDict.childNodes:
    if (bigDictItem.nodeType == xml.dom.Node.ELEMENT_NODE and
        bigDictItem.tagName == 'key' and
        bigDictItem.firstChild.data == 'Tracks'):
        tracksDict = getNextSibling(bigDictItem)
        assert tracksDict.tagName == 'dict', "need <dict> after 'Tracks'"
    if (bigDictItem.nodeType == xml.dom.Node.ELEMENT_NODE and
        bigDictItem.tagName == 'key' and
        bigDictItem.firstChild.data == 'Playlists'):
        plistArray = getNextSibling(bigDictItem)
        assert plistArray.tagName == 'array', "need <array> after 'Playlists'"
assert tracksDict, 'Could not find tracks dict'
#playlists can be empty, I guess, so we don't have an assert here
rlib = open(sys.argv[2], 'w')
rlists = open(sys.argv[3], 'w')
dlists = open(sys.argv[4], 'r')
ourdb = writeLibrary(rlib, tracksDict)
writePlaylists(rlists, dlists, plistArray, ourdb)

#####################
# drivemapping code #
#####################
# (commented out due to my decision to use a bash script, which does this
#  with a sed. If you want to resurrect this, just use convlocation() when getting
#  the location tag. - YZ)
#
# Use drivemapping to convert from the Windows drive letters found in your
# itunes database to your linux mountpoints.
#
# You'll definitely need to tweak the drivemapping dictionary to tell the script
# where your windows drives are mounted.
#
#
# If you don't mount a drive in linux and you want any files on that
# drive to be ignored instead of causing an error, set the mount point
# to None. For example: "localhost/C:" : None,
#drivemapping = { 
#                 "localhost/C:" : "/windows",
#                 "localhost/D:" : None,
#               }
#def convlocation( location ):
#    match = re.match(r"file://(\w+/[A-Z]:)(/.+)", location)
#    if not match:
#        sys.exit( "Invalid location: " + location )
#    drive = match.group(1)
#    path = match.group(2)
#    if not drivemapping.has_key( drive ):
#        sys.exit("Unknown drive: %s" % drive)
#    mapped_drive = drivemapping[drive]
#    if( mapped_drive == None ):
#        return None
#    if path[-1] == '/':
#        path = path[0:-1]
#    return "file://" + mapped_drive + path
