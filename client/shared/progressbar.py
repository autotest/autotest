"""
Basic text progress bar without fancy curses features
"""


__all__ = ['ProgressBar']


class ProgressBar:

    '''
    Displays interactively the progress of a given task

    Inspired/adapted from code.activestate.com recipe #168639
    '''

    DEFAULT_WIDTH = 77

    def __init__(self, minimum=0, maximum=100, width=DEFAULT_WIDTH, title=''):
        '''
        Initializes a new progress bar

        :type mininum: integer
        :param mininum: mininum (initial) value on the progress bar
        :type maximum: integer
        :param maximum: maximum (final) value on the progress bar
        :type width: integer
        :param with: number of columns, that is screen width
        '''
        assert maximum > minimum

        self.minimum = minimum
        self.maximum = maximum
        self.range = maximum - minimum
        self.width = width
        self.title = title

        self.current_amount = minimum
        self.update(minimum)

    def increment(self, increment, update_screen=True):
        '''
        Increments the current amount value
        '''
        self.update(self.current_amount + increment, update_screen)

    def update(self, amount, update_screen=True):
        '''
        Performs sanity checks and update the current amount
        '''
        if amount < self.minimum:
            amount = self.minimum
        if amount > self.maximum:
            amount = self.maximum
        self.current_amount = amount

        if update_screen:
            self.update_screen()

    def get_screen_text(self):
        '''
        Builds the actual progress bar text
        '''
        diff = float(self.current_amount - self.minimum)
        done = (diff / float(self.range)) * 100.0
        done = int(round(done))

        all = self.width - 2
        hashes = (done / 100.0) * all
        hashes = int(round(hashes))

        hashes_text = '#' * hashes
        spaces_text = ' ' * (all - hashes)
        screen_text = "[%s%s]" % (hashes_text, spaces_text)

        percent_text = "%s%%" % done
        percent_text_len = len(percent_text)
        percent_position = (len(screen_text) / 2) - percent_text_len

        screen_text = (screen_text[:percent_position] + percent_text +
                       screen_text[percent_position + percent_text_len:])

        if self.title:
            screen_text = '%s: %s' % (self.title,
                                      screen_text)
        return screen_text

    def update_screen(self):
        '''
        Prints the updated text to the screen
        '''
        print(self.get_screen_text(), '\r', end="")
