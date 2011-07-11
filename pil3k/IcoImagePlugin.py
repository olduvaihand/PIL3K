#
# The Python Imaging Library.
# $Id$
#
# Windows Icon support for PIL
#
# Notes:
#       uses BmpImagePlugin.py to read the bitmap data.
#
# History:
#       96-05-27 fl     Created
#
# Copyright (c) Secret Labs AB 1997.
# Copyright (c) Fredrik Lundh 1996.
#
# See the README file for information on usage and redistribution.
#


__version__ = "0.1"

import Image # from pil3k
import BmpImagePlugin # from pil3k


#
# --------------------------------------------------------------------

def i16(c):
    return c[0] + (c[1]<<8)

def i32(c):
    return c[0] + (c[1]<<8) + (c[2]<<16) + (c[3]<<24)


def _accept(prefix):
    return prefix[:4] == b'\x00\x00\x01\x00'

##
# Image plugin for Windows Icon files.

class IcoImageFile(BmpImagePlugin.BmpImageFile):

    format = "ICO"
    format_description = "Windows Icon"

    def _open(self):

        # check magic
        s = self.fp.read(6)
        if not _accept(s):
            raise SyntaxError("not an ICO file")

        # pick the largest icon in the file
        m = b""
        for i in range(i16(s[4:])):
            s = self.fp.read(16)
            if not m:
                m = s
            elif s[0] > m[0] and s[1] > m[1]:
                m = s
            #print("width", s[0])
            #print("height", s[1])
            #print("colors", s[2])
            #print("reserved", s[3])
            #print("planes", i16(s[4:]))
            #print("bitcount", i16(s[6:]))
            #print("bytes", i32(s[8:]))
            #print "offset", i32(s[12:]))

        # load as bitmap
        self._bitmap(i32(m[12:]))

        # patch up the bitmap height
        self.size = self.size[0], self.size[1]//2
        d, e, o, a = self.tile[0]
        self.tile[0] = d, (0,0)+self.size, o, a

        return


#
# --------------------------------------------------------------------

Image.register_open("ICO", IcoImageFile, _accept)

Image.register_extension("ICO", ".ico")
