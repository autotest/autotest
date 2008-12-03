"""Monkey patch lame-o vanilla unittest with test skip feature.

From the patch that was never applied (shameful!):
http://bugs.python.org/issue1034053
"""

import time, unittest


class SkipException(Exception):
    pass


def TestResult__init__(self):
    self.failures = []
    self.errors = []
    self.skipped = []
    self.testsRun = 0
    self.shouldStop = 0

unittest.TestResult.__init__ = TestResult__init__


def TestResult_addSkipped(self, test, err):
    """Called when a test is skipped.

    'err' is a tuple of values as returned by sys.exc_info().
    """
    self.skipped.append((test, str(err[1])))

unittest.TestResult.addSkipped = TestResult_addSkipped


def TestResult__repr__(self):
    return "<%s run=%i errors=%i failures=%i skipped=%i>" % (
        unittest._strclass(self.__class__), self.testsRun,
        len(self.errors), len(self.failures), len(self.skipped))

unittest.TestResult.__repr__ = TestResult__repr__


class TestCase(unittest.TestCase):
    # Yuck, all of run has to be copied for this.
    # I don't care about wrapping setUp atm.
    def run(self, result=None):
        if result is None: result = self.defaultTestResult()
        result.startTest(self)
        # Support variable naming differences between 2.4 and 2.6
        # Yay for silly variable hiding
        try:
            testMethodName = self.__testMethodName
            exc_info = self.__exc_info
        except AttributeError:
            testMethodName = self._testMethodName
            exc_info = self._exc_info

        testMethod = getattr(self, testMethodName)

        try:
            try:
                self.setUp()
            except KeyboardInterrupt:
                raise
            except:
                result.addError(self, exc_info())
                return

            ok = False
            try:
                testMethod()
                ok = True
            except self.failureException:
                result.addFailure(self, exc_info())
            except SkipException:
                result.addSkipped(self, exc_info())
            except KeyboardInterrupt:
                raise
            except:
                result.addError(self, exc_info())

            try:
                self.tearDown()
            except KeyboardInterrupt:
                raise
            except:
                result.addError(self, exc_info())
                ok = False
            if ok: result.addSuccess(self)
        finally:
            result.stopTest(self)


    def skip(self, msg=None):
        """Skip the test, with the given message."""
        raise SkipException(msg)


    def skipIf(self, expr, msg=None):
        """Skip the test if the expression is true."""
        if expr:
            raise SkipException(msg)


def _TextTestResult_addSkipped(self, test, err):
    unittest.TestResult.addSkipped(self, test, err)
    if self.showAll:
        msg = str(err[1])
        if msg:
            msg = " (" + msg + ")"
        self.stream.writeln("SKIPPED" + msg)
    elif self.dots:
        self.stream.write('S')

unittest._TextTestResult.addSkipped = _TextTestResult_addSkipped


# Bah
def TextTestRunner_run(self, test):
    "Run the given test case or test suite."
    result = self._makeResult()
    startTime = time.time()
    test(result)
    stopTime = time.time()
    timeTaken = stopTime - startTime
    result.printErrors()
    self.stream.writeln(result.separator2)
    run = result.testsRun
    self.stream.writeln("Ran %d test%s in %.3fs" %
                        (run, run != 1 and "s" or "", timeTaken))
    self.stream.writeln()
    if not result.wasSuccessful():
        self.stream.write("FAILED (")
        failed, errored, skipped = map(
            len, (result.failures, result.errors, result.skipped))
        if failed:
            self.stream.write("failures=%d" % failed)
        if errored:
            if failed: self.stream.write(", ")
            self.stream.write("errors=%d" % errored)
        if skipped:
            self.stream.write(", skipped=%d" % skipped)
        self.stream.writeln(")")
    else:
        if result.skipped:
            self.stream.writeln(
                "OK (skipped=%d)" % len(result.skipped))
        else:
            self.stream.writeln("OK")
    return result

unittest.TextTestRunner.run = TextTestRunner_run
