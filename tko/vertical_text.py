#!/usr/bin/env python

import gd, os, cStringIO, urllib2, sys

fontlist = [
    '/usr/lib/python/site-packages/reportlab/fonts/PenguinAttack.ttf'
    '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
    '/usr/share/fonts/truetype/ttf-bitstream-vera/Vera.ttf',
    ]

fontpath = '.'
for f in fontlist:
    if os.path.exists(f):
        fontpath = fontpath + ':' + os.path.dirname(f)
        FONT = os.path.basename(f)
        break

os.environ["GDFONTPATH"] = fontpath

try:
    FONT
except NameError:
    print "no fonts found"
    sys.exit(1)

def simple():
    im = gd.image((20,200))

    white = im.colorAllocate((255, 255, 255))
    black = im.colorAllocate((0, 0, 0))

    #im.colorTransparent(white)
    im.interlace(1)

    im.string_ttf(FONT, 10.0, 1.56, (15, 190), sys.argv[1], black)

    f=open(sys.argv[1]+".png","w")
    im.writePng(f)
    f.close()

simple()
