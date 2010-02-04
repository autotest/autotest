"""
Utility functions to deal with ppm (qemu screendump format) files.

@copyright: Red Hat 2008-2009
"""

import os, struct, time, re
from autotest_lib.client.bin import utils

# Some directory/filename utils, for consistency

def find_id_for_screendump(md5sum, dir):
    """
    Search dir for a PPM file whose name ends with md5sum.

    @param md5sum: md5 sum string
    @param dir: Directory that holds the PPM files.
    @return: The file's basename without any preceding path, e.g.
    '20080101_120000_d41d8cd98f00b204e9800998ecf8427e.ppm'.
    """
    try:
        files = os.listdir(dir)
    except OSError:
        files = []
    for file in files:
        exp = re.compile(r"(.*_)?" + md5sum + r"\.ppm", re.IGNORECASE)
        if exp.match(file):
            return file


def generate_id_for_screendump(md5sum, dir):
    """
    Generate a unique filename using the given MD5 sum.

    @return: Only the file basename, without any preceding path. The
    filename consists of the current date and time, the MD5 sum and a .ppm
    extension, e.g. '20080101_120000_d41d8cd98f00b204e9800998ecf8427e.ppm'.
    """
    filename = time.strftime("%Y%m%d_%H%M%S") + "_" + md5sum + ".ppm"
    return filename


def get_data_dir(steps_filename):
    """
    Return the data dir of the given steps filename.
    """
    filename = os.path.basename(steps_filename)
    return os.path.join(os.path.dirname(steps_filename), "..", "steps_data",
                        filename + "_data")


# Functions for working with PPM files

def image_read_from_ppm_file(filename):
    """
    Read a PPM image.

    @return: A 3 element tuple containing the width, height and data of the
            image.
    """
    fin = open(filename,"rb")
    l1 = fin.readline()
    l2 = fin.readline()
    l3 = fin.readline()
    data = fin.read()
    fin.close()

    (w, h) = map(int, l2.split())
    return (w, h, data)


def image_write_to_ppm_file(filename, width, height, data):
    """
    Write a PPM image with the given width, height and data.

    @param filename: PPM file path
    @param width: PPM file width (pixels)
    @param height: PPM file height (pixels)
    """
    fout = open(filename,"wb")
    fout.write("P6\n")
    fout.write("%d %d\n" % (width, height))
    fout.write("255\n")
    fout.write(data)
    fout.close()


def image_crop(width, height, data, x1, y1, dx, dy):
    """
    Crop an image.

    @param width: Original image width
    @param height: Original image height
    @param data: Image data
    @param x1: Desired x coordinate of the cropped region
    @param y1: Desired y coordinate of the cropped region
    @param dx: Desired width of the cropped region
    @param dy: Desired height of the cropped region
    @return: A 3-tuple containing the width, height and data of the
    cropped image.
    """
    if x1 > width - 1: x1 = width - 1
    if y1 > height - 1: y1 = height - 1
    if dx > width - x1: dx = width - x1
    if dy > height - y1: dy = height - y1
    newdata = ""
    index = (x1 + y1*width) * 3
    for i in range(dy):
        newdata += data[index:(index+dx*3)]
        index += width*3
    return (dx, dy, newdata)


def image_md5sum(width, height, data):
    """
    Return the md5sum of an image.

    @param width: PPM file width
    @param height: PPM file height
    @data: PPM file data
    """
    header = "P6\n%d %d\n255\n" % (width, height)
    hash = utils.hash('md5', header)
    hash.update(data)
    return hash.hexdigest()


def get_region_md5sum(width, height, data, x1, y1, dx, dy,
                      cropped_image_filename=None):
    """
    Return the md5sum of a cropped region.

    @param width: Original image width
    @param height: Original image height
    @param data: Image data
    @param x1: Desired x coord of the cropped region
    @param y1: Desired y coord of the cropped region
    @param dx: Desired width of the cropped region
    @param dy: Desired height of the cropped region
    @param cropped_image_filename: if not None, write the resulting cropped
            image to a file with this name
    """
    (cw, ch, cdata) = image_crop(width, height, data, x1, y1, dx, dy)
    # Write cropped image for debugging
    if cropped_image_filename:
        image_write_to_ppm_file(cropped_image_filename, cw, ch, cdata)
    return image_md5sum(cw, ch, cdata)


def image_verify_ppm_file(filename):
    """
    Verify the validity of a PPM file.

    @param filename: Path of the file being verified.
    @return: True if filename is a valid PPM image file. This function
    reads only the first few bytes of the file so it should be rather fast.
    """
    try:
        size = os.path.getsize(filename)
        fin = open(filename, "rb")
        assert(fin.readline().strip() == "P6")
        (width, height) = map(int, fin.readline().split())
        assert(width > 0 and height > 0)
        assert(fin.readline().strip() == "255")
        size_read = fin.tell()
        fin.close()
        assert(size - size_read == width*height*3)
        return True
    except:
        return False


def image_comparison(width, height, data1, data2):
    """
    Generate a green-red comparison image from two given images.

    @param width: Width of both images
    @param height: Height of both images
    @param data1: Data of first image
    @param data2: Data of second image
    @return: A 3-element tuple containing the width, height and data of the
            generated comparison image.

    @note: Input images must be the same size.
    """
    newdata = ""
    i = 0
    while i < width*height*3:
        # Compute monochromatic value of current pixel in data1
        pixel1_str = data1[i:i+3]
        temp = struct.unpack("BBB", pixel1_str)
        value1 = int((temp[0] + temp[1] + temp[2]) / 3)
        # Compute monochromatic value of current pixel in data2
        pixel2_str = data2[i:i+3]
        temp = struct.unpack("BBB", pixel2_str)
        value2 = int((temp[0] + temp[1] + temp[2]) / 3)
        # Compute average of the two values
        value = int((value1 + value2) / 2)
        # Scale value to the upper half of the range [0, 255]
        value = 128 + value / 2
        # Compare pixels
        if pixel1_str == pixel2_str:
            # Equal -- give the pixel a greenish hue
            newpixel = [0, value, 0]
        else:
            # Not equal -- give the pixel a reddish hue
            newpixel = [value, 0, 0]
        newdata += struct.pack("BBB", newpixel[0], newpixel[1], newpixel[2])
        i += 3
    return (width, height, newdata)


def image_fuzzy_compare(width, height, data1, data2):
    """
    Return the degree of equality of two given images.

    @param width: Width of both images
    @param height: Height of both images
    @param data1: Data of first image
    @param data2: Data of second image
    @return: Ratio equal_pixel_count / total_pixel_count.

    @note: Input images must be the same size.
    """
    equal = 0.0
    different = 0.0
    i = 0
    while i < width*height*3:
        pixel1_str = data1[i:i+3]
        pixel2_str = data2[i:i+3]
        # Compare pixels
        if pixel1_str == pixel2_str:
            equal += 1.0
        else:
            different += 1.0
        i += 3
    return equal / (equal + different)
