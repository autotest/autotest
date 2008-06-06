import traceback

from autotest_lib.tko import status_lib, utils as tko_utils


class parser(object):
    """
    Abstract parser base class. Provides a generic implementation of the
    standard parser interfaction functions. The derived classes must
    implement a state_iterator method for this class to be useful.
    """
    def start(self, job):
        """ Initialize the parser for processing the results of
        'job'."""
        # initialize all the basic parser parameters
        self.job = job
        self.finished = False
        self.line_buffer = status_lib.line_buffer()
        # create and prime the parser state machine
        self.state = self.state_iterator(self.line_buffer)
        self.state.next()


    def process_lines(self, lines):
        """ Feed 'lines' into the parser state machine, and return
        a list of all the new test results produced."""
        self.line_buffer.put_multiple(lines)
        try:
            return self.state.next()
        except StopIteration:
            msg = ("WARNING: parser was called to process status "
                   "lines after it was end()ed\n"
                   "Current traceback:\n" +
                   traceback.format_exc() +
                   "\nCurrent stack:\n" +
                   "".join(traceback.format_stack()))
            tko_utils.dprint(msg)
            return []


    def end(self, lines=[]):
        """ Feed 'lines' into the parser state machine, signal to the
        state machine that no more lines are forthcoming, and then
        return a list of all the new test results produced."""
        self.line_buffer.put_multiple(lines)
        # run the state machine to clear out the buffer
        self.finished = True
        try:
            return self.state.next()
        except StopIteration:
            msg = ("WARNING: parser was end()ed multiple times\n"
                   "Current traceback:\n" +
                   traceback.format_exc() +
                   "\nCurrent stack:\n" +
                   "".join(traceback.format_stack()))
            tko_utils.dprint(msg)
            return []


    @staticmethod
    def make_job(dir):
        """ Create a new instance of the job model used by the
        parser, given a results directory."""
        raise NotImplemented


    def state_iterator(self, buffer):
        """ A generator method that implements the actual parser
        state machine. """
        raise NotImplemented
