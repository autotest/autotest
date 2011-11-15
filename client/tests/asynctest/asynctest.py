import os, re, time

from autotest_lib.client.bin import utils, test

class asynctest(test.test):
    version = 1

    def run_once(self):
        #We create 2 processes to show that progress continues on each independently
        x = utils.AsyncJob("sleep 1 && echo hi && sleep 1 && echo hi && sleep 1 && echo hi && sleep 1")
        y = utils.AsyncJob("sleep 100")
        time.sleep(2)
        print "Process 1 stdout is now %s" % x.get_stdout()
        res = x.wait_for()
        print "Process 1 result object is: %s" % res

        t = time.time()
        y.wait_for(timeout=1)
        print "Process 2 took %d to be killed" % (time.time()-t)
