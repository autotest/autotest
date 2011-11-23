"""
Video Maker transforms screenshots taken during a test into a HTML 5
compatible video, so that one can watch the screen activity of the
whole test from inside your own browser.

This relies on generally available multimedia libraries, frameworks
and tools.
"""


import os, time, glob, logging


__all__ = ['GstPythonVideoMaker', 'video_maker']


#
# Check what kind of video libraries tools we have available
#
# Gstreamer python bindings are our first choice
try:
    import gst
    GST_PYTHON_INSTALLED = True
except ImportError:
    GST_PYTHON_INSTALLED = False


#
# PIL is also required to normalize images
#
try:
    import PIL.Image
    PIL_INSTALLED = True
except ImportError:
    PIL_INSTALLED = False


#
# We only do video
#
CONTAINER_PREFERENCE = ['ogg', 'webm']
ENCODER_PREFERENCE = ['theora', 'vp8']


class GstPythonVideoMaker(object):
    '''
    Makes a movie out of screendump images using gstreamer-python
    '''


    CONTAINER_MAPPING = {'ogg' : 'oggmux',
                         'webm' : 'webmmux'}

    ENCODER_MAPPING = {'theora' : 'theoraenc',
                       'vp8' : 'vp8enc'}

    CONTAINER_ENCODER_MAPPING = {'ogg' : 'theora',
                                 'webm' : 'vp8'}


    def __init__(self, verbose=False):
        if not GST_PYTHON_INSTALLED:
            raise ValueError('gstreamer-python library was not found')
        if not PIL_INSTALLED:
            raise ValueError('python-imaging library was not found')

        self.verbose = verbose


    def get_most_common_image_size(self, input_dir):
        '''
        Find the most common image size
        '''
        image_sizes = {}
        image_files = glob.glob(os.path.join(input_dir, '*.jpg'))
        for f in image_files:
            i = PIL.Image.open(f)
            if not image_sizes.has_key(i.size):
                image_sizes[i.size] = 1
            else:
                image_sizes[i.size] += 1

        most_common_size_counter = 0
        most_common_size = None
        for image_size, image_counter in image_sizes.items():
            if image_counter > most_common_size_counter:
                most_common_size_counter = image_counter
                most_common_size = image_size
        return most_common_size


    def normalize_images(self, input_dir):
        '''
        GStreamer requires all images to be the same size, so we do it here
        '''
        image_size = self.get_most_common_image_size(input_dir)
        if image_size is None:
            image_size = (800, 600)

        if self.verbose:
            logging.debug('Normalizing image files to size: %s', image_size)
        image_files = glob.glob(os.path.join(input_dir, '*.jpg'))
        for f in image_files:
            i = PIL.Image.open(f)
            if i.size != image_size:
                i.resize(image_size).save(f)


    def has_element(self, kind):
        '''
        Returns True if a gstreamer element is available
        '''
        return gst.element_factory_find(kind) is not None


    def get_container_name(self):
        '''
        Gets the video container available that is the best based on preference
        '''
        for c in CONTAINER_PREFERENCE:
            element_kind = self.CONTAINER_MAPPING.get(c, c)
            if self.has_element(element_kind):
                return element_kind

        raise ValueError('No suitable container format was found')


    def get_encoder_name(self):
        '''
        Gets the video encoder available that is the best based on preference
        '''
        for c in ENCODER_PREFERENCE:
            element_kind = self.ENCODER_MAPPING.get(c, c)
            if self.has_element(element_kind):
                return element_kind

        raise ValueError('No suitable encoder format was found')


    def get_element(self, name):
        '''
        Makes and returns and element from the gst factory interface
        '''
        if self.verbose:
            logging.debug('GStreamer element requested: %s', name)
        return gst.element_factory_make(name, name)


    def start(self, input_dir, output_file):
        '''
        Process the input files and output the video file
        '''
        self.normalize_images(input_dir)
        no_files = len(glob.glob(os.path.join(input_dir, '*.jpg')))
        if self.verbose:
            logging.debug('Number of files to encode as video: %s', no_files)

        pipeline = gst.Pipeline("pipeline")

        source = self.get_element("multifilesrc")
        source_location = os.path.join(input_dir, "%04d.jpg")
        if self.verbose:
            logging.debug("Source location: %s", source_location)
        source.set_property('location', source_location)
        source.set_property('index', 1)
        source_caps = gst.Caps()
        source_caps.append('image/jpeg,framerate=(fraction)4/1')
        source.set_property('caps', source_caps)

        decoder = self.get_element("jpegdec")

        # Attempt to auto detect the chosen encoder/mux based on output_file
        encoder = None
        container = None

        for container_name in self.CONTAINER_ENCODER_MAPPING:
            if output_file.endswith('.%s' % container_name):

                enc_name = self.CONTAINER_ENCODER_MAPPING[container_name]
                enc_name_gst = self.ENCODER_MAPPING[enc_name]
                encoder = self.get_element(enc_name_gst)

                cont_name_gst = self.CONTAINER_MAPPING[container_name]
                container = self.get_element(cont_name_gst)

        # If auto detection fails, choose from the list of preferred codec/mux
        if encoder is None:
            encoder = self.get_element(self.get_encoder_name())
        if container is None:
            container = self.get_element(self.get_container_name())

        output = self.get_element("filesink")
        output.set_property('location', output_file)

        pipeline.add_many(source, decoder, encoder, container, output)
        gst.element_link_many(source, decoder, encoder, container, output)

        pipeline.set_state(gst.STATE_PLAYING)
        while True:
            if source.get_property('index') <= no_files:
                if self.verbose:
                    logging.debug("Currently processing image number: %s",
                                  source.get_property('index'))
                time.sleep(1)
            else:
                break
        time.sleep(3)
        pipeline.set_state(gst.STATE_NULL)


def video_maker(input_dir, output_file):
    '''
    Instantiates and runs a video maker
    '''
    v = GstPythonVideoMaker()
    v.start(input_dir, output_file)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print 'Usage: %s <input_dir> <output_file>' % sys.argv[0]
    else:
        video_maker(sys.argv[1], sys.argv[2])
