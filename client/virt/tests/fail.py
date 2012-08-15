import logging
from autotest.client.shared import error
from autotest.client.virt import utils_test


def run_fail(test, params, env):
    """Raise TestFail exception"""
    raise error.TestFail("Fail test is failing!")
