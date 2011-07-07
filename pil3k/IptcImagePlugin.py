#
# The Python Imaging Library.
# $Id$
#
# IPTC/NAA file handling
#
# history:
# 1995-10-01 fl   Created
# 1998-03-09 fl   Cleaned up and added to PIL
# 2002-06-18 fl   Added getiptcinfo helper
#
# Copyright (c) Secret Labs AB 1997-2002.
# Copyright (c) Fredrik Lundh 1995.
#
# See the README file for information on usage and redistribution.
#


__version__ = "0.3"


import Image # from pil3k
import ImageFile # from pil3k

import os
import tempfile


COMPRESSION = {
    1: "raw",
    5: "jpeg"
}

PAD = b'x00' * 4

#
# Helpers

def i16(c):
    return c[1] + (c[0]<<8)

def i32(c):
    return c[3] + (c[2]<<8) + (c[1]<<16) + (c[0]<<24)

def i(c):
    return i32((PAD + bytes((c,))[-4:])

def dump(c):
    for i in c:
        print("{0:02x}".format(i,), end=" ")
    print("\n")

##
# Image plugin for IPTC/NAA datastreams.  To read IPTC/NAA fields
# from TIFF and JPEG files, use the <b>getiptcinfo</b> function.

class IptcImageFile(ImageFile.ImageFile):

    format = "IPTC"
    format_description = "IPTC/NAA"

    def getint(self, key):
        return i(self.info[key])

    def field(self):
        #
        # get a IPTC field header
        s = self.fp.read(5)
        if not len(s):
            return None, 0

        tag = s[1], s[2]

        # syntax
        if s[0] != 0x1C or tag[0] < 1 or tag[0] > 9:
            raise SyntaxError("invalid IPTC/NAA file")

        # field size
        size = s[3]
        if size > 132:
            raise IOError("illegal field length in IPTC/NAA file")
        elif size == 128:
            size = 0
        elif size > 128:
            size = i(self.fp.read(size-128))
        else:
            size = i16(s[3:])

        return tag, size

    def _is_raw(self, offset, size):
        #
        # check if the file can be mapped

        # DISABLED: the following only slows things down...
        return 0

        self.fp.seek(offset)
        t, sz = self.field()
        if sz != size[0]:
            return 0
        y = 1
        while True:
            self.fp.seek(sz, 1)
            t, s = self.field()
            if t != (8, 10):
                break
            if s != sz:
                return 0
            y = y + 1
        return y == size[1]

    def _open(self):

        # load descriptive fields
        while True:
            offset = self.fp.tell()
            tag, size = self.field()
            if not tag or tag == (8,10):
                break
            if size:
                tagdata = self.fp.read(size)
            else:
                tagdata = None
            if tag in self.info.keys():
                if isinstance(self.info[tag], list):
                    self.info[tag].append(tagdata)
                else:
                    self.info[tag] = [self.info[tag], tagdata]
            else:
                self.info[tag] = tagdata

            # print(tag, self.info[tag])

        # mode
        layers = self.info[(3,60)][0]
        component = self.info[(3,60)][1]
        if (3,65) in self.info:
            id = self.info[(3,65)][0]-1
        else:
            id = 0
        if layers == 1 and not component:
            self.mode = "L"
        elif layers == 3 and component:
            self.mode = "RGB"[id]
        elif layers == 4 and component:
            self.mode = "CMYK"[id]

        # size
        self.size = self.getint((3,20)), self.getint((3,30))

        # compression
        try:
            compression = COMPRESSION[self.getint((3,120))]
        except KeyError:
            raise IOError("Unknown IPTC image compression")

        # tile
        if tag == (8,10):
            if compression == "raw" and self._is_raw(offset, self.size):
                self.tile = [(compression, (offset, size + 5, -1),
                             (0, 0, self.size[0], self.size[1]))]
            else:
                self.tile = [("iptc", (compression, offset),
                             (0, 0, self.size[0], self.size[1]))]

    def load(self):

        if len(self.tile) != 1 or self.tile[0][0] != b"iptc":
            return ImageFile.ImageFile.load(self)

        type, tile, box = self.tile[0]

        encoding, offset = tile

        self.fp.seek(offset)

        # Copy image data to temporary file
        outfile = tempfile.mktemp()
        o = open(outfile, "wb")
        if encoding == "raw":
            # To simplify access to the extracted file,
            # prepend a PPM header
            o.write("P5\n{0} {1}\n255\n".format(*self.size).encode('latin_1',
                errors='replace'))
        while True:
            type, size = self.field()
            if type != (8, 10):
                break
            while size > 0:
                s = self.fp.read(min(size, 8192))
                if not s:
                    break
                o.write(s)
                size = size - len(s)
        o.close()

        try:
            try:
                # fast
                self.im = Image.core.open_ppm(outfile)
            except:
                # slightly slower
                im = Image.open(outfile)
                im.load()
                self.im = im.im
        finally:
            try:
                os.unlink(outfile)
            except:
                pass


Image.register_open("IPTC", IptcImageFile)

Image.register_extension("IPTC", ".iim")

##
# Get IPTC information from TIFF, JPEG, or IPTC file.
#
# @param im An image containing IPTC data.
# @return A dictionary containing IPTC information, or None if
#     no IPTC information block was found.

def getiptcinfo(im):

    import TiffImagePlugin # from pil3k
    import JpegImagePlugin # from pil3k
    import io

    data = None

    if isinstance(im, IptcImageFile):
        # return info dictionary right away
        return im.info

    elif isinstance(im, JpegImagePlugin.JpegImageFile):
        # extract the IPTC/NAA resource
        try:
            app = im.app["APP13"]
            if app[:14] == b"Photoshop 3.0\x00":
                app = app[14:]
                # parse the image resource block
                offset = 0
                while app[offset:offset+4] == b"8BIM":
                    offset = offset + 4
                    # resource code
                    code = JpegImagePlugin.i16(app, offset)
                    offset = offset + 2
                    # resource name (usually empty)
                    name_len = app[offset]
                    name = app[offset+1:offset+1+name_len]
                    offset = 1 + offset + name_len
                    if offset & 1:
                        offset = offset + 1
                    # resource data block
                    size = JpegImagePlugin.i32(app, offset)
                    offset = offset + 4
                    if code == 0x0404:
                        # 0x0404 contains IPTC/NAA data
                        data = app[offset:offset+size]
                        break
                    offset = offset + size
                    if offset & 1:
                        offset = offset + 1
        except (AttributeError, KeyError):
            pass

    elif isinstance(im, TiffImagePlugin.TiffImageFile):
        # get raw data from the IPTC/NAA tag (PhotoShop tags the data
        # as 4-byte integers, so we cannot use the get method...)
        try:
            type, data = im.tag.tagdata[TiffImagePlugin.IPTC_NAA_CHUNK]
        except (AttributeError, KeyError):
            pass

    if data is None:
        return None # no properties

    # create an IptcImagePlugin object without initializing it
    class FakeImage(object):
        pass
    im = FakeImage()
    im.__class__ = IptcImageFile

    # parse the IPTC information chunk
    im.info = {}
    im.fp = io.BytesIO(data)

    try:
        im._open()
    except (IndexError, KeyError):
        pass # expected failure

    return im.info
